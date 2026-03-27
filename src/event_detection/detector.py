"""
detector.py — LangChain Tool-Calling Agent for Event Detection

Architecture:
  1. Build user-turn content using BaseMessages (SystemMessage + Human/AIMessage history)
  2. Bind two tools to the LLM:
       - publish_event       → sends a new bot message
       - update_previous_event → edits the most recent bot message in-place
  3. Run the agent and handle whichever tool call it makes.
"""

import json
import re
from typing import Any, Callable, Awaitable

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from src.logger import get_logger
from src.event_detection.prompts import get_system_prompt
from src.event_detection.runtime import ActionContext, get_graph_app, register_action_context, unregister_action_context

logger = get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# Reply formatter helper (imported lazily to avoid circular imports)
# ─────────────────────────────────────────────────────────────────────────────

async def _build_reply(
    points: list[dict],
    sender_id: str,
    sender_name: str,
    sender_db: dict,
    platform: str,
    chat_id: str,
    ctx_logger: Any,
    footer: str | None = None,
    filter_members_fn: Callable[[list[dict]], Awaitable[list[dict]]] | None = None,
) -> str | None:
    """Build the formatted conversion reply string, or None if no members."""
    from src.storage import storage
    from src import formatter

    members = await storage.get_chat_members(chat_id, platform=platform)
    if filter_members_fn:
        members = await filter_members_fn(members)
    if not members:
        ctx_logger.warning(f"[chat:{chat_id}] No members in DB, skipping reply.")
        return None

    conversions = []
    for point in points:
        time_str = point.get("time")
        city_override = point.get("city")

        if city_override:
            from src.geo import aget_timezone_by_city
            geo_result = await aget_timezone_by_city(city_override)
            if geo_result and not geo_result.get("error"):
                source_city = geo_result["city"]
                source_tz = geo_result["timezone"]
                source_flag = geo_result["flag"]
            else:
                source_city = sender_db.get("city")
                source_tz = sender_db.get("timezone")
                source_flag = sender_db.get("flag", "")
        else:
            source_city = sender_db.get("city")
            source_tz = sender_db.get("timezone")
            source_flag = sender_db.get("flag", "")

        if not source_tz:
            ctx_logger.debug(f"[chat:{chat_id}] No source TZ for point {point}, skipping.")
            continue

        conversions.append({
            "original_time": time_str,
            "source_city": source_city,
            "source_tz": source_tz,
            "source_flag": source_flag,
            "event_type": point.get("event_type", "событие"),
        })

    if not conversions:
        return None

    return formatter.format_multi_conversion(
        conversions=conversions, members=members, sender_name=sender_name, footer=footer
    )


# ─────────────────────────────────────────────────────────────────────────────
# Text thought parsing and fallback JSON parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_reflections_from_text(text: str) -> dict:
    ref_dict = {"event_logic": "", "time_logic": "", "geo_logic": "", "tool_logic": ""}
    if not text:
        return ref_dict
    for key in ref_dict.keys():
        match = re.search(rf"<{key}>(.*?)</{key}>", text, re.IGNORECASE | re.DOTALL)
        if match:
            ref_dict[key] = match.group(1).strip()
    return ref_dict

def _parse_llm_json(raw: str, ctx_logger: Any) -> dict:
    """Parse a raw JSON string from the LLM into a normalised result dict."""
    try:
        # Use regex to find the first JSON-like object to handle trailing tags or text
        import re
        json_match = re.search(r'(\{.*\})', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
        else:
            data = json.loads(raw)
        reflections = data.get("reflections", {})
        points = data.get("points", [])
        times = [p["time"] for p in points] if isinstance(points, list) else []
        cities = [p["city"] for p in points] if isinstance(points, list) else []
        event_types = (
            [p.get("event_type", "событие") for p in points]
            if isinstance(points, list) else []
        )
        return {
            "reflections": {
                "event_logic": str(reflections.get("event_logic", "")),
                "time_logic": str(reflections.get("time_logic", "")),
                "geo_logic": str(reflections.get("geo_logic", "")),
            },
            "event": bool(data.get("event", False)),
            "sender_id": str(data.get("sender_id", "")),
            "sender_name": str(data.get("sender_name", "")),
            "time": times,
            "city": cities,
            "event_type": event_types,
            "points": points,
        }
    except Exception as exc:
        ctx_logger.error(f"LLM JSON parse error: {exc}. Raw: {raw}")
        return {
            "reflections": {},
            "event": False,
            "sender_id": "",
            "sender_name": "",
            "time": [],
            "city": [],
            "event_type": [],
            "points": [],
        }


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Main detect_event — LangChain agent entry point
# ─────────────────────────────────────────────────────────────────────────────

async def detect_event(
    current_msg: dict,
    snapshot: list,   # Kept for signature compatibility, but mostly ignored by Graph
    sender_db: dict,
    send_fn: Callable[[str], Awaitable[str | None]] | None = None,
    edit_fn: Callable[[str, str], Awaitable[None]] | None = None,
    delete_fn: Callable[[str], Awaitable[None]] | None = None,
    filter_members_fn: Callable[[list[dict]], Awaitable[list[dict]]] | None = None,
    platform: str = "",
    chat_id: str = "",
    ctx_logger: Any = None,
) -> dict:
    """
    LangChain tool-calling agent for event detection.
    
    Now uses LangGraph (StateGraph) with AsyncSqliteSaver. Memory is preserved in sqlite!
    We use One-Shot routing natively handled by 'action_node' in graph.py.
    """
    if ctx_logger is None:
        ctx_logger = logger

    sender_id = current_msg.get("author_id", "")
    sender_name = current_msg.get("author_name", "Unknown")
    anchor = current_msg.get("timestamp_utc", "")
    current_text = current_msg.get("text", "")
    sender_registered = bool(sender_db and sender_db.get("timezone"))

    # Build Context
    system_text = get_system_prompt()
    system_text += f"\n\n--- CURRENT CONTEXT ---\nSENDER: id={sender_id} name={sender_name}\nANCHOR (CURRENT) TIME: {anchor}\n"

    ts_str = f"[{anchor}] " if anchor else ""
    human_msg = HumanMessage(content=f"{ts_str}[Author: {sender_name}]: {current_text}")

    # Build reply closure for tools
    async def build_reply_wrapper(points: list[dict], footer: str | None = None) -> str | None:
        return await _build_reply(
            points,
            sender_id,
            sender_name,
            sender_db,
            platform,
            chat_id,
            ctx_logger,
            footer=footer,
            filter_members_fn=filter_members_fn,
        )

    import uuid
    
    thread_id = f"{platform}_{chat_id}"
    use_snapshot_context = platform == "eval"
    if use_snapshot_context:
        thread_id = f"{platform}_ephemeral_{uuid.uuid4().hex[:8]}"

    config = {
        "configurable": {
            "thread_id": thread_id,
            "system_prompt": system_text,
            "chat_id": chat_id,
            "platform": platform,
            "sender_registered": sender_registered,
        },
        "recursion_limit": 5, # Limits error loops to 1 retry (llm -> action -> llm -> action -> END)
    }

    try:
        app = await get_graph_app()
        register_action_context(
            thread_id,
            ActionContext(
                send_fn=send_fn,
                edit_fn=edit_fn,
                delete_fn=delete_fn,
                build_reply_fn=build_reply_wrapper,
                chat_id=chat_id,
                platform=platform,
                sender_registered=sender_registered,
            ),
        )

        # For production chat threads we rely on the persisted LangGraph thread
        # state. Eval mode can still seed a temporary thread from a supplied snapshot.
        if use_snapshot_context:
            input_messages = snapshot + [human_msg] if snapshot else [human_msg]
        else:
            input_messages = [human_msg]

        response_state = await app.ainvoke({"messages": input_messages}, config)

        # Check results
        messages = response_state.get("messages", [])
        last_msg = messages[-1] if messages else None

        result_points = []
        tool_used = ""
        message_id = None
        reasoning = ""
        event_ref = None
        comment = None

        if last_msg and isinstance(last_msg, ToolMessage):
            # Retrieve the tool call arguments and reasoning from the previous AIMessage
            for i in range(len(messages) - 2, -1, -1):
                if isinstance(messages[i], AIMessage) and messages[i].tool_calls:
                    tc = messages[i].tool_calls[0]
                    if tc["id"] == last_msg.tool_call_id:
                        result_points = tc["args"].get("points", [])
                        # Reasoning: prefer structured arg, fallback to AIMessage.content
                        reasoning = tc["args"].get("reasoning", "") or messages[i].content or ""
                        # event_ref specific to update_previous_event
                        event_ref = tc["args"].get("event_ref", None)
                        comment = tc["args"].get("comment", None)
                        tool_used = tc["name"]
                        break

            message_id = last_msg.additional_kwargs.get("message_id")
        elif last_msg and isinstance(last_msg, AIMessage) and last_msg.content:
            # LLM outputted JSON string instead of calling tool (fallback scenario)
            raw = last_msg.content
            # Use regex or simple check to see if there's text before JSON
            json_start = raw.find("{")
            if json_start != -1:
                reasoning = raw[:json_start].strip()
                json_str = raw[json_start:]
                parsed = _parse_llm_json(json_str, ctx_logger)
            else:
                reasoning = raw.strip()
                parsed = {
                    "event": False,
                    "points": [],
                    "reflections": _parse_reflections_from_text(reasoning),
                    "time": [], "city": [], "event_type": [],
                    "sender_id": sender_id, "sender_name": sender_name
                }

            if parsed.get("event") and send_fn:
                result_points = parsed.get("points", [])
                tool_used = "publish_event"
                message_id = await send_fn(await build_reply_wrapper(result_points))

            parsed["reasoning"] = reasoning
            parsed["message_published"] = bool(message_id)
            if not parsed.get("reflections"):
                parsed["reflections"] = _parse_reflections_from_text(reasoning)
            return parsed

        event_detected = bool(result_points and tool_used)
        parsed_ref = _parse_reflections_from_text(reasoning)

        return {
            "reflections": parsed_ref,
            "reasoning": reasoning,
            "event": event_detected,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "time": [p.get("time", "") for p in result_points],
            "city": [p.get("city") for p in result_points],
            "event_type": [p.get("event_type", "событие") for p in result_points],
            "points": result_points,
            "tool_used": tool_used,
            "message_id": message_id,
            "message_published": bool(message_id),
            "event_ref": event_ref,
            "comment": comment,
        }

    except Exception as exc:
        ctx_logger.error(f"[chat:{chat_id}] Graph Agent error: {exc}")
        return {
            "reflections": {},
            "event": False,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "time": [],
            "city": [],
            "event_type": [],
            "points": [],
            "message_published": False,
        }
    finally:
        unregister_action_context(thread_id)
