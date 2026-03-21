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
import logging
import os
from typing import Any, Callable, Awaitable

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, trim_messages

from src.logger import get_logger
from src.event_detection.client import get_llm_model
from src.event_detection.prompts import get_system_prompt, EVENT_DETECTION_SCHEMA
from src.event_detection.history import get_last_bot_message_id
from src.config import get_bot_settings, get_log_llm_prompts

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
) -> str | None:
    """Build the formatted conversion reply string, or None if no members."""
    from src.storage import storage
    from src import formatter

    members = await storage.get_chat_members(chat_id, platform=platform)
    if not members:
        ctx_logger.warning(f"[chat:{chat_id}] No members in DB, skipping reply.")
        return None

    conversions = []
    for point in points:
        time_str = point.get("time")
        city_override = point.get("city")

        if city_override:
            from src.geo import get_timezone_by_city
            geo_result = get_timezone_by_city(city_override)
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
        conversions=conversions, members=members, sender_name=sender_name
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agent fallback: parse JSON if the model returns JSON instead of a tool call
# ─────────────────────────────────────────────────────────────────────────────

def _parse_llm_json(raw: str, ctx_logger: Any) -> dict:
    """Parse a raw JSON string from the LLM into a normalised result dict."""
    try:
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
# Main detect_event — LangChain agent entry point
# ─────────────────────────────────────────────────────────────────────────────

async def detect_event(
    current_msg: dict,
    snapshot: list,
    sender_db: dict,
    send_fn: Callable[[str], Awaitable[str | None]] | None = None,
    edit_fn: Callable[[str, str], Awaitable[None]] | None = None,
    platform: str = "",
    chat_id: str = "",
    ctx_logger: Any = None,
) -> dict:
    """
    LangChain tool-calling agent for event detection.
    
    Now uses 2026 Core Message management:
      - Uses BaseMessage (SystemMessage, HumanMessage, AIMessage)
      - Slices history heavily
      - Trims tokens properly to save costs
    """
    if ctx_logger is None:
        ctx_logger = logger

    sender_id = current_msg.get("author_id", "")
    sender_name = current_msg.get("author_name", "Unknown")
    anchor = current_msg.get("timestamp_utc", "")
    current_text = current_msg.get("text", "")

    # Prepend Context to System
    system_text = get_system_prompt()
    system_text += f"\n\n--- CURRENT CONTEXT ---\nSENDER: id={sender_id} name={sender_name}\nANCHOR (CURRENT) TIME: {anchor}\n"

    messages = [SystemMessage(content=system_text)]
    messages.extend(snapshot)

    # Append the actual message that triggered the bot
    ts_str = f"[{anchor}] " if anchor else ""
    messages.append(HumanMessage(content=f"{ts_str}[{sender_name}]: {current_text}"))

    if get_log_llm_prompts():
        # Cleanly format messages for debug output
        debug_str = "\n".join(
            f"[{m.__class__.__name__}]: {m.content[:200]}" for m in messages
        )
        ctx_logger.info(f"\n🚀 [LLM PROMPT LOG MODE] 🚀\n{debug_str}\n" + "-" * 42)
    else:
        ctx_logger.debug(f"LLM call | msg='{current_text[:60]}'")

    # ── Build tools ──────────────────────────────────────────────────────────

    async def _do_publish(points: list[dict]) -> str | None:
        """Build reply and send as a NEW message."""
        reply = await _build_reply(
            points, sender_id, sender_name, sender_db, platform, chat_id, ctx_logger
        )
        if reply and send_fn:
            message_id = await send_fn(reply)
            ctx_logger.info(
                f"[chat:{chat_id}] publish_event: sent new message "
                f"(id={message_id}, points={len(points)})"
            )
            return message_id
        return None

    async def _do_update(points: list[dict]) -> str | None:
        """Build reply and EDIT the most recent bot message."""
        prev_id = get_last_bot_message_id(platform, chat_id)
        reply = await _build_reply(
            points, sender_id, sender_name, sender_db, platform, chat_id, ctx_logger
        )
        if reply and prev_id and edit_fn:
            try:
                await edit_fn(prev_id, reply)
                ctx_logger.info(
                    f"[chat:{chat_id}] update_previous_event: edited message "
                    f"(id={prev_id}, points={len(points)})"
                )
                return prev_id
            except Exception as e:
                ctx_logger.warning(
                    f"[chat:{chat_id}] edit failed ({e}), falling back to publish"
                )
        return await _do_publish(points)

    @tool
    def publish_event(points: list[dict]) -> str:
        """
        Call this tool when the current message contains a NEW time event
        that has not been published yet, or when there is no previous bot message
        to update.

        Args:
            points: List of event points, each with 'time' (HH:MM), optional 'city',
                    and 'event_type' (e.g. 'созвон', 'дедлайн').
        """
        import asyncio
        return asyncio.get_event_loop().run_until_complete(_do_publish(points)) or ""

    @tool
    def update_previous_event(points: list[dict]) -> str:
        """
        Call this tool when the current message OVERRIDES or REFINES a time that
        the bot already published (visible as [BOT]: detected: ... in HISTORY).
        This edits the previous bot message in-place instead of flooding the chat.

        Args:
            points: Updated event points with corrected time/city/event_type.
        """
        import asyncio
        return asyncio.get_event_loop().run_until_complete(_do_update(points)) or ""

    # ── LangChain model setup ────────────────────────────────────────────────
    settings = get_bot_settings()
    temp = settings.get("llm", {}).get("temperature", 0.0)
    model_name = get_llm_model()

    llm = ChatOpenAI(
        model=model_name,
        temperature=temp,
        openai_api_base=os.getenv("LLM_BASE_URL") or None,
        openai_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or "no-key",
    )
    tools_list = [publish_event, update_previous_event]
    llm_with_tools = llm.bind_tools(tools_list)

    # ── Apply Trim Policies ──────────────────────────────────────────────────
    
    # 1. Trim by count (limit to max 10 messages + 1 system msg max)
    limit = settings.get("event_detection", {}).get("context_messages", 5)
    if len(messages) > limit + 1:
        messages = [messages[0]] + messages[-limit:]

    # 2. Trim strictly by tokens
    def rough_token_counter(msgs: list) -> int:
        # A fast robust heuristic: ~4 characters per token
        return sum(len(str(m.content)) // 4 for m in msgs)

    try:
        trimmed_messages = trim_messages(
            messages,
            max_tokens=2500, # Large ENOUGH for the system prompt, tight enough for history
            strategy="last",
            token_counter=rough_token_counter,
            include_system=True,
            allow_partial=False
        )
    except Exception as e:
        ctx_logger.error(f"Error trimming messages: {e}")
        trimmed_messages = messages


    # ── Invoke agent ─────────────────────────────────────────────────────────
    result_points: list[dict] = []
    tool_used: str = ""
    message_id: str | None = None

    try:
        response = await llm_with_tools.ainvoke(trimmed_messages)

        if response.tool_calls:
            tc = response.tool_calls[0]
            tool_used = tc["name"]
            args = tc["args"]
            points = args.get("points", [])
            result_points = points

            if tool_used == "publish_event":
                message_id = await _do_publish(points)
            elif tool_used == "update_previous_event":
                message_id = await _do_update(points)

        else:
            raw = response.content or ""
            if raw.strip().startswith("{"):
                parsed = _parse_llm_json(raw, ctx_logger)
                if parsed.get("event") and send_fn:
                    result_points = parsed.get("points", [])
                    tool_used = "publish_event"
                    message_id = await _do_publish(result_points)
                return parsed

    except Exception as exc:
        ctx_logger.error(f"[chat:{chat_id}] Agent error: {exc}")
        return {
            "reflections": {},
            "event": False,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "time": [],
            "city": [],
            "event_type": [],
            "points": [],
        }

    # ── Build result dict ─────────────────────────────────────────────────────
    event_detected = bool(result_points and tool_used)
    return {
        "reflections": {},
        "event": event_detected,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "time": [p.get("time", "") for p in result_points],
        "city": [p.get("city") for p in result_points],
        "event_type": [p.get("event_type", "событие") for p in result_points],
        "points": result_points,
        "tool_used": tool_used,
        "message_id": message_id,
    }
