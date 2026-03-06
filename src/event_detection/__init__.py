from src.event_detection.history import append_to_history, get_chat_lock
from src.event_detection.detector import detect_event
from src.capture import should_call_llm

async def process_message(
    message_text: str,
    chat_id: str,
    user_id: str,
    platform: str,
    author_name: str,
    timestamp_utc: str
) -> dict:
    """
    Main entry point for the LLM Event Detection pipeline.
    
    Returns a dictionary matching EVENT_DETECTION_SCHEMA:
    {
      "trigger": bool,
      "polarity": "positive" | "negative",
      "confidence": float,
      "reason": str,
      "times": list[str],
      "event_location": str | None
    }
    """
    
    # Pack the normalized message data
    msg_data = {
        "platform": platform,
        "chat_id": chat_id,
        "author_id": user_id,
        "author_name": author_name,
        "text": message_text.strip(),
        "timestamp_utc": timestamp_utc
    }
    
    # 1. Take snapshot of N preceding messages and append current message to deque
    snapshot = append_to_history(platform, chat_id, msg_data)

    # 2. Optional Prefilter check (Cost saving)
    if not should_call_llm(message_text):
        return {
            "trigger": False,
            "polarity": "negative",
            "confidence": 1.0,
            "reason": "Skipped by prefilter",
            "times": [],
            "event_location": None
        }

    # 3. Acquire chat lock so LLM calls are sequential per chat
    lock = get_chat_lock(platform, chat_id)
    if lock.locked():
        # Chat is already processing a previous message. 
        # This message is in the deque for future context but we skip analyzing it 
        # as a trigger itself to prevent race conditions.
        return {
            "trigger": False, 
            "confidence": 0.0, 
            "times": [], 
            "event_location": None,
            "reason": "Skipped due to concurrent chat lock"
        }
        
    async with lock:
        # 4. Detect event using LLM (Pass 1 + optional Pass 2)
        result = await detect_event(msg_data, snapshot)
        
    return result

__all__ = ["process_message"]
