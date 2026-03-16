import datetime
from src.config import get_max_message_age, get_max_message_hard_skip
from src.logger import get_logger
from src.event_detection.history import append_to_history, get_chat_lock
from src.event_detection.detector import detect_event

logger = get_logger()

async def process_message(
    message_text: str,
    chat_id: str,
    user_id: str,
    platform: str,
    author_name: str,
    timestamp_utc: str,
    sender_db: dict | None = None,
    send_fn=None,  # async callable(text: str) → None
    skip_history_append: bool = False,
    skip_aging: bool = False,
    precomputed_snapshot: list[dict] | None = None,
) -> dict:
    """
    Main entry point for the LLM pipeline with queuing and aging.
    """
    # 0. Hard skip for excessively long messages (security / cost protection)
    hard_limit = get_max_message_hard_skip()
    if len(message_text) > hard_limit:
        logger.warning(f"[{platform}:{chat_id}] Message too long ({len(message_text)} chars), hard skipping.")
        return {
            "event": False, "sender_id": user_id, "sender_name": author_name,
            "time": [], "city": [], "reason": f"Message exceeded hard limit of {hard_limit} chars",
        }

    msg_data = {
        "platform":      platform,
        "chat_id":       chat_id,
        "author_id":     user_id,
        "author_name":   author_name,
        "text":          message_text.strip(),
        "timestamp_utc": timestamp_utc,
    }

    # 1. Aging check before even trying to append to history
    if not skip_aging:
        max_age = get_max_message_age()
        try:
            msg_time = datetime.datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
            now = datetime.datetime.now(datetime.timezone.utc)
            diff = (now - msg_time).total_seconds()
            logger.debug(f"[{platform}:{chat_id}] Message age check: diff={diff:.2f}s, max_age={max_age}s")
            if diff > max_age:
                logger.warning(f"[{platform}:{chat_id}] Message too old ({int(diff)}s), skipping.")
                return {
                    "event": False, "sender_id": user_id, "sender_name": author_name,
                    "time": [], "city": [], "reason": "Message stale before processing",
                }
        except Exception as e:
            logger.error(f"[{platform}:{chat_id}] Error checking message age: {e}")
    
    # Pre-parse time for second aging check below
    try:
        msg_time = datetime.datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
    except:
        msg_time = datetime.datetime.now(datetime.timezone.utc)

    if skip_history_append:
        snapshot = precomputed_snapshot or []
        logger.debug(f"[{platform}:{chat_id}] Using precomputed snapshot (size={len(snapshot)})")
    else:
        snapshot = append_to_history(platform, chat_id, msg_data)

    # 2. Waiting lock - one LLM call at a time per chat
    lock = get_chat_lock(platform, chat_id)
    
    async with lock:
        # Re-check aging after getting the lock (it might have been waiting for a while)
        if not skip_aging:
            max_age = get_max_message_age()
            now = datetime.datetime.now(datetime.timezone.utc)
            age = (now - msg_time).total_seconds()
            if age > max_age:
                logger.warning(
                    f"[{platform}:{chat_id}] Message became stale while waiting in queue. "
                    f"Age: {int(age)}s (Limit: {max_age}s). Dropping msg from '{author_name}'."
                )
                return {
                    "event": False, "sender_id": user_id, "sender_name": author_name,
                    "time": [], "city": [], "reason": f"Message stale after queueing ({int(age)}s)",
                }

        result = await detect_event(
            current_msg=msg_data,
            snapshot=snapshot,
            sender_db=sender_db or {},
            send_fn=send_fn,
            platform=platform,
            chat_id=chat_id,
        )

    return result

__all__ = ["process_message"]
