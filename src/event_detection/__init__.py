import datetime
import logging
from typing import Dict, Any
from src.config import get_max_message_age, get_max_message_hard_skip
from src.logger import get_logger
from src.event_detection.detector import detect_event

logger = get_logger()


async def _build_reply(
    *,
    points: list[dict],
    sender_db: Dict[str, Any],
    sender_name: str,
    platform: str,
    chat_id: str,
    ctx_logger: logging.LoggerAdapter,
) -> str | None:
    """Build a formatted reply from structured detection output."""
    from src import formatter
    from src.geo import async_get_timezone_by_city
    from src.storage import storage

    members = await storage.get_chat_members(chat_id, platform=platform)
    if not members:
        ctx_logger.warning(f"No members in DB for chat {chat_id}, skipping reply.")
        return None

    conversions = []
    for point in points:
        city_override = point.get("city")
        if city_override:
            geo_result = await async_get_timezone_by_city(city_override)
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
            ctx_logger.debug(f"No source timezone for point {point}, skipping.")
            continue

        conversions.append(
            {
                "original_time": point.get("time"),
                "source_city": source_city,
                "source_tz": source_tz,
                "source_flag": source_flag,
                "event_title": point.get("event_title"),
            }
        )

    if not conversions:
        return None

    return formatter.format_multi_conversion(
        conversions=conversions,
        members=members,
        sender_name=sender_name,
    )


async def process_message(
    message_text: str,
    chat_id: str,
    user_id: str,
    platform: str,
    author_name: str,
    timestamp_utc: str,
    sender_db: Dict | None = None,
    skip_aging: bool = False,
) -> Dict[str, Any]:
    """
    Main entry point for the LLM pipeline with aging.
    """
    # Create a contextual logger for this message
    ctx_logger = logging.LoggerAdapter(
        logger, {"extra_prefix": f"[{platform}:{chat_id}]"}
    )

    ctx_logger.info(f"Processing message from {author_name} ({user_id})")

    # 0. Hard skip for excessively long messages (security / cost protection)
    hard_limit = get_max_message_hard_skip()
    if len(message_text) > hard_limit:
        ctx_logger.warning(
            f"Message too long ({len(message_text)} chars), hard skipping."
        )
        return {
            "event": False,
            "sender_id": user_id,
            "sender_name": author_name,
            "time": [],
            "city": [],
            "reason": f"Message exceeded hard limit of {hard_limit} chars",
        }

    msg_data = {
        "platform": platform,
        "chat_id": chat_id,
        "author_id": user_id,
        "author_name": author_name,
        "text": message_text.strip(),
        "timestamp_utc": timestamp_utc,
    }

    # 1. Aging check 
    if not skip_aging:
        max_age = get_max_message_age()
        try:
            msg_time = datetime.datetime.fromisoformat(timestamp_utc)
            if msg_time.tzinfo is None:
                msg_time = msg_time.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            diff = (now - msg_time).total_seconds()
            logger.debug(
                f"[{platform}:{chat_id}] Message age check: diff={diff:.2f}s, max_age={max_age}s"
            )
            if diff > max_age:
                logger.warning(
                    f"[{platform}:{chat_id}] Message too old ({int(diff)}s), skipping."
                )
                return {
                    "event": False,
                    "sender_id": user_id,
                    "sender_name": author_name,
                    "time": [],
                    "city": [],
                    "reason": "Message stale before processing",
                }
        except Exception as e:
            logger.error(f"[{platform}:{chat_id}] Error checking message age: {e}")

    # Run current-message event detection via the OpenAI-compatible LLM client
    result = await detect_event(
        current_msg=msg_data,
        chat_id=chat_id,
        ctx_logger=ctx_logger,
    )

    reply_text = None
    points = result.get("points", [])
    if result.get("event") and points and sender_db:
        reply_text = await _build_reply(
            points=points,
            sender_db=sender_db,
            sender_name=author_name,
            platform=platform,
            chat_id=chat_id,
            ctx_logger=ctx_logger,
        )

    result["reply_text"] = reply_text

    return result

__all__ = ["process_message"]
