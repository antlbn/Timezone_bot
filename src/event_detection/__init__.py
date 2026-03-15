from src.event_detection.history import append_to_history, get_chat_lock
from src.event_detection.detector import detect_event


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
    precomputed_snapshot: list[dict] | None = None,
) -> dict:
    """
    Main entry point for the LLM pipeline.

    Parameters
    ----------
    message_text : Raw message text from the adapter.
    chat_id      : Platform chat / guild ID (string).
    user_id      : Platform user ID (string).
    platform     : "telegram" | "discord"
    author_name  : Display name of the sender.
    timestamp_utc: ISO 8601 UTC timestamp of the message.
    sender_db    : Sender's DB record (timezone, city, flag, …).
                   Must be pre-fetched by the adapter; None = sender unknown.
    send_fn      : Async callable that posts a text reply to the chat.
                   Required for the tool path; if None, detection runs but no reply is sent.

    Returns a dict with at minimum:
        { event: bool, time: list[str], city: list[str|None],
          sender_id: str, sender_name: str }
    """

    msg_data = {
        "platform":      platform,
        "chat_id":       chat_id,
        "author_id":     user_id,
        "author_name":   author_name,
        "text":          message_text.strip(),
        "timestamp_utc": timestamp_utc,
    }

    if skip_history_append:
        snapshot = precomputed_snapshot or []
        logger.debug(f"[chat:{chat_id}] Using precomputed snapshot (size={len(snapshot)})")
    else:
        # 1. Snapshot N preceding messages, then append current message to deque
        snapshot = append_to_history(platform, chat_id, msg_data)

    # 2. Per-chat lock — one LLM call at a time per chat
    lock = get_chat_lock(platform, chat_id)
    
    # If it's a normal message (not recovery), fail fast if locked
    if not skip_history_append and lock.locked():
        return {
            "event":       False,
            "sender_id":   user_id,
            "sender_name": author_name,
            "time":        [],
            "city":        [],
            "reason":      "Skipped due to concurrent chat lock",
        }

    # If it's a recovery message, we WAIT for the lock to ensure it's processed
    async with lock:
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
