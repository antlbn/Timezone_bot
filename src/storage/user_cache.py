"""
User Snapshot Cache (Layer 1 of Working Memory).
Read-through cache for user data from SQLite.
"""
from src.storage import storage
from src.logger import get_logger

logger = get_logger()

# In-memory snapshot: {(user_id, platform): user_data_dict}
_users_snapshot = {}

async def get_user_cached(user_id: int, platform: str) -> dict | None:
    """
    Get user data from cache. If not present, load from SQLite.
    """
    key = (user_id, platform)
    if key in _users_snapshot:
        return _users_snapshot[key]
    
    user = await storage.get_user(user_id, platform)
    if user:
        _users_snapshot[key] = user
        logger.debug(f"User {user_id} ({platform}) cached in snapshot.")
    return user

def invalidate_user_cache(user_id: int, platform: str):
    """
    Remove user from cache. Call this after set_user.
    """
    key = (user_id, platform)
    if key in _users_snapshot:
        del _users_snapshot[key]
        logger.debug(f"User {user_id} ({platform}) cache invalidated.")
