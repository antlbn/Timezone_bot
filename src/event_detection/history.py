import asyncio
from collections import deque
from src.config import get_bot_settings

# Keyed by (platform, chat_id)
# Value is a fast ring-buffer of dicts representing N historical messages
_message_history: dict[tuple[str, str], deque] = {}

# Locks to ensure only one LLM request fires per chat at a given time
_chat_locks: dict[tuple[str, str], asyncio.Lock] = {}

def _get_history_limit() -> int:
    """Read the extended context limit from config, defaulting to 3."""
    settings = get_bot_settings()
    return settings.get("event_detection", {}).get("extended_context_messages", 3)

def _get_max_chars() -> int:
    """Read max characters per message limit from config, defaulting to 500."""
    settings = get_bot_settings()
    return settings.get("event_detection", {}).get("max_message_length_chars", 500)

def append_to_history(platform: str, chat_id: str, message_data: dict) -> list[dict]:
    """
    Appends a new message to the chat's short-term history.
    Returns a snapshot of the N messages BEFORE this one was added
    for use in Pass 2 of the LLM Event Detection.
    """
    key = (platform, str(chat_id))
    limit = _get_history_limit()
    max_chars = _get_max_chars()
    
    # Truncate text to protect LLM context windows
    if "text" in message_data and len(message_data["text"]) > max_chars:
        message_data["text"] = message_data["text"][:max_chars] + "...[truncated]"

    if key not in _message_history:
        _message_history[key] = deque(maxlen=limit)
    
    dq = _message_history[key]
    
    # Take a frozen snapshot BEFORE mutating the deque.
    # We use this frozen context for Pass 2 so it doesn't jump around
    # while the LLM is running asynchronously.
    snapshot = list(dq)
    
    # Push the new message into the live deque
    dq.append(message_data)
    
    return snapshot

def get_chat_lock(platform: str, chat_id: str) -> asyncio.Lock:
    """
    Retrieves the unique asyncio lock for the specified chat.
    Used to prevent overlapping LLM queries.
    """
    key = (platform, str(chat_id))
    if key not in _chat_locks:
        _chat_locks[key] = asyncio.Lock()
    return _chat_locks[key]

def format_snapshot_for_llm(snapshot: list[dict]) -> str:
    """
    Converts a snapshot list of message dicts into a human-readable string
    for the LLM prompt.
    """
    lines = []
    for msg in snapshot:
        author = msg.get("author_name", "Unknown")
        text = msg.get("text", "")
        # The payload contains standard UTC timestamp from the adapters
        lines.append(f"[{author}]: {text}")
        
    if not lines:
        return "No prior conversational context."
        
    return "\n".join(lines)
