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

# Structure: {(user_id, platform): {"data": dict, "expires": float}}
_frozen_messages = {}

async def save_pending_message(user_id: int, platform: str, message_data: dict):
    """
    Save message data to in-memory 'frozen' storage for onboarding.
    """
    timeout = get_onboarding_timeout()
    expires = time.time() + timeout
    
    _frozen_messages[(user_id, platform)] = {
        "data": message_data,
        "expires": expires
    }
    logger.info(f"Saved pending message for {user_id} ({platform}). TTL: {timeout}s.")

async def get_and_delete_pending_message(user_id: int, platform: str) -> dict | None:
    """
    Retrieve and remove the pending message for a user.
    Checks for expiration.
    """
    key = (user_id, platform)
    if key not in _frozen_messages:
        return None
    
    item = _frozen_messages.pop(key)
    if time.time() > item["expires"]:
        logger.warning(f"Pending message for {user_id} ({platform}) expired.")
        return None
    
    return item["data"]

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
