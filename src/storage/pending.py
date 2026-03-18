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

# Track when we last sent a DM invite to avoid spamming: {(user_id, platform): timestamp}
_dm_invite_timestamps: dict[tuple[int, str], float] = {}


async def should_send_dm_invite(user_id: int, platform: str, cooldown: int) -> bool:
    """Check if enough time has passed since we last invited this user to DM onboarding."""
    key = (user_id, platform)
    last_sent = _dm_invite_timestamps.get(key, 0)
    return (time.time() - last_sent) >= cooldown


async def mark_dm_invite_sent(user_id: int, platform: str):
    """Record that we just sent a DM onboarding invite to this user."""
    _dm_invite_timestamps[(user_id, platform)] = time.time()


async def clear_dm_invite(user_id: int, platform: str):
    """Clear the DM invite cooldown for a user (e.g. after successful onboarding)."""
    _dm_invite_timestamps.pop((user_id, platform), None)


async def cleanup_loop():
    """
    Background task to clean up expired frozen messages and stale invite timestamps.
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
        # Also clean up very old invite timestamps (> 24h) to prevent unbounded growth
        stale_invites = [
            k for k, ts in _dm_invite_timestamps.items()
            if (now - ts) > 86400
        ]
        for k in stale_invites:
            _dm_invite_timestamps.pop(k, None)
