import asyncio

# Locks to ensure only one LLM request fires per chat at a given time.
_chat_locks: dict[tuple[str, str], asyncio.Lock] = {}


def get_chat_lock(platform: str, chat_id: str) -> asyncio.Lock:
    """Retrieve the unique asyncio lock for the specified chat."""
    key = (platform, str(chat_id))
    if key not in _chat_locks:
        _chat_locks[key] = asyncio.Lock()
    return _chat_locks[key]
