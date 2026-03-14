import json
from src.logger import get_logger
from src.event_detection.client import get_llm_client, get_llm_model
from src.event_detection.prompts import get_system_prompt, get_tools
from src.config import get_bot_settings

logger = get_logger()


def _build_user_content(
    current_msg: dict,
    snapshot: list[dict],
    sender_db: dict,
) -> str:
    """
    Compose the plain-text user-turn block that goes to the LLM.

    Format:
        SENDER: id=<id>  name=<name>  timezone=<tz>
        ANCHOR: <timestamp_utc>

        HISTORY:
        [Author]: text
        ...

        CURRENT MESSAGE:
        [Author]: text
    """
    sender_id = current_msg.get("author_id", "")
    sender_name = current_msg.get("author_name", "Unknown")
    anchor = current_msg.get("timestamp_utc", "")

    lines = [
        f"SENDER: id={sender_id}  name={sender_name}",
        f"ANCHOR: {anchor}",
        "",
        "HISTORY:",
    ]

    if snapshot:
        for msg in snapshot:
            lines.append(f"[{msg.get('author_name', 'Unknown')}]: {msg.get('text', '')}")
    else:
        lines.append("(no prior messages)")

    lines += [
        "",
        "CURRENT MESSAGE:",
        f"[{sender_name}]: {current_msg.get('text', '')}",
    ]

    return "\n".join(lines)


async def call_llm(messages: list[dict], tools: list[dict]) -> object:
    """Call the configured LLM and return the raw response choice."""
    client = get_llm_client()
    model = get_llm_model()
    settings = get_bot_settings()
    temp = settings.get("llm", {}).get("temperature", 0.0)

    kwargs: dict = dict(
        model=model,
        messages=messages,
        temperature=temp,
        response_format={"type": "json_object"},
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
        # json_object mode is incompatible with tool_choice on some providers;
        # remove it when tools are active so the provider picks the right format.
        del kwargs["response_format"]

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0]


def _parse_llm_json(raw_json: str) -> dict:
    """Parse and validate LLM JSON, filling safe defaults on failure."""
    try:
        data = json.loads(raw_json)
        reflections = data.get("reflections", {})
        points = data.get("points", [])
        times = [p["time"] for p in points] if isinstance(points, list) else []
        cities = [p["city"] for p in points] if isinstance(points, list) else []
        
        return {
            "reflections": {
                "event_logic": str(reflections.get("event_logic", "")),
                "time_logic":  str(reflections.get("time_logic", "")),
                "geo_logic":   str(reflections.get("geo_logic", "")),
            },
            "event":       bool(data.get("event", False)),
            "sender_id":   str(data.get("sender_id", "")),
            "sender_name": str(data.get("sender_name", "")),
            "time":        times,
            "city":        cities,
        }
    except Exception as exc:
        logger.error(f"LLM JSON parse error: {exc}. Raw: {raw_json}")
        return {
            "reflections": {},
            "event": False,
            "sender_id": "",
            "sender_name": "",
            "time": [],
            "city": [],
        }


async def detect_event(
    current_msg: dict,
    snapshot: list[dict],
    sender_db: dict,
    send_fn=None,
    platform: str = "",
    chat_id: str = "",
) -> dict:
    """
    Single-pass LLM orchestration.

    1. Build prompt with SENDER block + HISTORY snapshot + CURRENT MESSAGE.
    2. Call LLM (with convert_time tool registered).
    3a. If LLM returned a tool_call → dispatch to tools.execute_convert_time().
    3b. Else → parse JSON response and return it.

    Returns the parsed detection dict (regardless of whether a tool was called).
    """
    user_content = _build_user_content(current_msg, snapshot, sender_db)
    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user",   "content": user_content},
    ]

    logger.debug(f"LLM call | chat={chat_id} | msg='{current_msg.get('text', '')[:60]}'")

    choice = await call_llm(messages, tools=get_tools())

    # ── Tool-call path ──────────────────────────────────────────────────────
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        tool_call = choice.message.tool_calls[0]
        if tool_call.function.name == "convert_time":
            try:
                args = json.loads(tool_call.function.arguments)
            except Exception as exc:
                logger.error(f"Failed to parse tool_call args: {exc}")
                return {"event": False, "time": [], "city": [], "sender_id": "", "sender_name": ""}

            points = args.get("points", [])
            times = [p["time"] for p in points] if isinstance(points, list) else []
            cities = [p["city"] for p in points] if isinstance(points, list) else []

            logger.info(
                f"[chat:{chat_id}] Tool call: convert_time | "
                f"sender={args.get('sender_id')} times={times} cities={cities}"
            )

            if send_fn:
                from src.event_detection.tools import execute_convert_time
                await execute_convert_time(
                    sender_id=args.get("sender_id", ""),
                    sender_name=args.get("sender_name", ""),
                    times=times,
                    cities=cities,
                    sender_db=sender_db,
                    platform=platform,
                    chat_id=chat_id,
                    send_fn=send_fn,
                )

            # Return a synthetic result so callers can log/test it
            return {
                "event":       True,
                "sender_id":   args.get("sender_id", ""),
                "sender_name": args.get("sender_name", ""),
                "time":        times,
                "city":        cities,
                "reflections": {"event_logic": "tool_call dispatched", "time_logic": "", "geo_logic": ""},
            }

    # ── JSON-response path (no tool call / tool not supported by provider) ──
    raw = choice.message.content or ""
    result = _parse_llm_json(raw)

    # If the LLM returned event=true but no tool_call, invoke the tool ourselves
    # (happens when a provider doesn't support function-calling)
    if result["event"] and result["time"] and send_fn:
        logger.info(
            f"[chat:{chat_id}] JSON-path tool dispatch | "
            f"sender={result['sender_id']} times={result['time']}"
        )
        from src.event_detection.tools import execute_convert_time
        await execute_convert_time(
            sender_id=result["sender_id"],
            sender_name=result["sender_name"],
            times=result["time"],
            cities=result["city"],
            sender_db=sender_db,
            platform=platform,
            chat_id=chat_id,
            send_fn=send_fn,
        )

    return result
