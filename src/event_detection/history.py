import asyncio
from collections import defaultdict
from src.config import get_bot_settings
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

# Keyed by (platform, chat_id)
# Value is a fast ring-buffer of native LangChain messages
_message_history: dict[tuple[str, str], InMemoryChatMessageHistory] = defaultdict(InMemoryChatMessageHistory)

# Locks to ensure only one LLM request fires per chat at a given time
_chat_locks: dict[tuple[str, str], asyncio.Lock] = {}


def _get_history_limit() -> int:
    """Read the context limit from config, defaulting to 5."""
    settings = get_bot_settings()
    return settings.get("event_detection", {}).get("context_messages", 5)


def _get_max_chars() -> int:
    """Read max characters per message limit from config, defaulting to 500."""
    settings = get_bot_settings()
    return settings.get("event_detection", {}).get("max_message_length_chars", 500)


def append_to_history(platform: str, chat_id: str, message_data: dict) -> list:
    """
    Appends a new message to the chat's short-term history.
    Returns a snapshot of the messages BEFORE this one was added
    for use in Pass 2 of the LLM Event Detection.
    """
    key = (platform, str(chat_id))
    history = _message_history[key]

    # Take a frozen snapshot BEFORE mutating the history.
    snapshot = list(history.messages)

    # Determine if this is a BOT message or human
    author_id = message_data.get("author_id")
    text = message_data.get("text", "")
    
    if author_id == "BOT":
        msg = AIMessage(
            content=f"[BOT]: {text}",
            additional_kwargs={"message_id": message_data.get("message_id")}
        )
        history.add_message(msg)
    else:
        author_name = message_data.get("author_name", "Unknown")
        ts = message_data.get("timestamp_utc", "")
        ts_str = f"[{ts}] " if ts else ""
        msg = HumanMessage(content=f"{ts_str}[{author_name}]: {text}")
        history.add_message(msg)


    # Simple memory leak prevention (keep at most 100 recent messages)
    if len(history.messages) > 100:
        history.messages = history.messages[-100:]

    return snapshot


def get_last_bot_message_id(platform: str, chat_id: str) -> str | None:
    """
    Scan the history (newest first) and return the message_id
    of the most recent BOT record, or None if none exists.
    Used by the update_previous_event tool to find the message to edit.
    """
    key = (platform, str(chat_id))
    if key not in _message_history:
        return None
        
    history = _message_history[key]
    for msg in reversed(history.messages):
        if isinstance(msg, AIMessage) and msg.additional_kwargs.get("message_id"):
            return msg.additional_kwargs["message_id"]
    return None


def get_chat_lock(platform: str, chat_id: str) -> asyncio.Lock:
    """
    Retrieves the unique asyncio lock for the specified chat.
    Used to prevent overlapping LLM queries.
    """
    key = (platform, str(chat_id))
    if key not in _chat_locks:
        _chat_locks[key] = asyncio.Lock()
    return _chat_locks[key]

