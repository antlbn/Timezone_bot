import datetime
import logging
from typing import List, Dict, Any, Callable
from src.config import get_max_message_age, get_max_message_hard_skip
from src.logger import get_logger
from src.event_detection.detector import detect_event

logger = get_logger()


async def process_message(
    message_text: str,
    chat_id: str,
    user_id: str,
    platform: str,
    author_name: str,
    timestamp_utc: str,
    sender_db: Dict | None = None,
    send_fn: Callable | None = None, 
    edit_fn: Callable | None = None, 
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

    # Process via Langchain Model Call directly
    result = await detect_event(
        current_msg=msg_data,
        sender_db=sender_db or {},
        send_fn=send_fn,
        edit_fn=edit_fn,
        platform=platform,
        chat_id=chat_id,
        ctx_logger=ctx_logger,
    )

    return result

__all__ = ["process_message"]
