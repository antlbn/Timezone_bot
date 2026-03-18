import json
from src.logger import get_logger
from src.event_detection.client import get_llm_client, get_llm_model
from src.event_detection.prompts import get_system_prompt
from typing import Any
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


async def call_llm(messages: list[dict]) -> object:
    """Call the configured LLM and return the raw response choice."""
    client = get_llm_client()
    model = get_llm_model()
    settings = get_bot_settings()
    temp = settings.get("llm", {}).get("temperature", 0.0)

    # Use JSON Mode for reliable structured output
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temp,
        response_format={"type": "json_object"},
    )
    return response.choices[0]


def _parse_llm_json(raw_json: str, ctx_logger: Any) -> dict:
    """Parse and validate LLM JSON, filling safe defaults on failure."""
    try:
        data = json.loads(raw_json)
        reflections = data.get("reflections", {})
        points = data.get("points", [])
        
        # Backward compatibility / internal formatting
        times = [p["time"] for p in points] if isinstance(points, list) else []
        cities = [p["city"] for p in points] if isinstance(points, list) else []
        event_types = [p.get("event_type", "событие") for p in points] if isinstance(points, list) else []
        
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
            "event_type":  event_types,
            "points":      points,
        }
    except Exception as exc:
        ctx_logger.error(f"LLM JSON parse error: {exc}. Raw: {raw_json}")
        return {
            "reflections": {},
            "event": False,
            "sender_id": "",
            "sender_name": "",
            "time": [],
            "city": [],
            "points": [],
        }


async def detect_event(
    current_msg: dict,
    snapshot: list[dict],
    sender_db: dict,
    send_fn=None,
    platform: str = "",
    chat_id: str = "",
    ctx_logger: Any = None, # Added ctx_logger parameter
) -> dict:
    """
    Direct JSON Event Detection.
    
    1. Build prompt with SENDER block + HISTORY snapshot + CURRENT MESSAGE.
    2. Call LLM (forcing JSON mode).
    3. Parse JSON response.
    4. If event=true, execute the conversion logic directly.
    """
    if ctx_logger is None:
        ctx_logger = logger # Fallback to global logger if not provided

    user_content = _build_user_content(current_msg, snapshot, sender_db)
    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user",   "content": user_content},
    ]

    ctx_logger.debug(f"LLM call | msg='{current_msg.get('text', '')[:60]}'")

    choice = await call_llm(messages)
    raw = ""
    if hasattr(choice, "message") and choice.message:
        raw = choice.message.content or ""
    
    
    result = _parse_llm_json(raw, ctx_logger=ctx_logger)

    if result["event"] and result["points"] and send_fn:
        ctx_logger.info(
            f"Actionable event detected via JSON | "
            f"sender={result['sender_id']} points_count={len(result['points'])}"
        )
        from src.event_detection.tools import execute_convert_time
        await execute_convert_time(
            sender_id=result["sender_id"],
            sender_name=result["sender_name"],
            points=result["points"],
            sender_db=sender_db,
            platform=platform,
            chat_id=chat_id,
            send_fn=send_fn,
        )

    return result
