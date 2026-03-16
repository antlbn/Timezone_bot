"""
In-Memory Pending Storage (Layer 4 of Working Memory).
Stores messages for users currently in the onboarding flow.
Replaces Redis-based storage.
"""
import time
import asyncio
from src.config import get_onboarding_timeout
from src.logger import get_logger

logger = get_logger()

# Structure: {(user_id, platform): {"messages": List[dict], "expires": float}}
_frozen_messages = {}

async def save_pending_message(user_id: int, platform: str, message_data: dict):
    """
    Save message data to in-memory 'frozen' storage for onboarding.
    Appends if entry exists and is not expired.
    """
    key = (user_id, platform)
    timeout = get_onboarding_timeout()
    now = time.time()
    
    if key in _frozen_messages and now < _frozen_messages[key]["expires"]:
        # Entry exists and is fresh — just append
        _frozen_messages[key]["messages"].append(message_data)
        logger.info(f"Appended pending message for {user_id} ({platform}). Total: {len(_frozen_messages[key]['messages'])}")
    else:
        # Create new entry or replace expired one
        _frozen_messages[key] = {
            "messages": [message_data],
            "expires": now + timeout
        }
        logger.info(f"Started new pending queue for {user_id} ({platform}). TTL: {timeout}s.")

async def get_and_delete_pending_messages(user_id: int, platform: str) -> list[dict]:
    """
    Retrieve and remove ALL pending messages for a user.
    Checks for expiration.
    """
    key = (user_id, platform)
    if key not in _frozen_messages:
        return []
    
    item = _frozen_messages.pop(key)
    if time.time() > item["expires"]:
        logger.warning(f"Pending messages for {user_id} ({platform}) expired.")
        return []
    
    return item["messages"]

async def peek_pending_messages(user_id: int, platform: str) -> list[dict]:
    """
    Look at pending messages without deleting them.
    Checks for expiration.
    """
    key = (user_id, platform)
    if key not in _frozen_messages:
        return []
    
    item = _frozen_messages[key]
    if time.time() > item["expires"]:
        return []
    
    return item["messages"]

async def cleanup_loop():
    """
    Background task to clean up expired frozen messages.
    """
    while True:
        await asyncio.sleep(60)
        now = time.time()
        to_delete = [
            k for k, v in _frozen_messages.items() 
            if now > v["expires"]
        ]
        for k in to_delete:
            _frozen_messages.pop(k, None)
            logger.debug(f"Cleaned up expired frozen message for {k}.")
