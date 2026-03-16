from collections import OrderedDict
from src.storage import storage
from src.logger import get_logger

logger = get_logger()

# In-memory LRU snapshot: {(user_id, platform): user_data_dict}
CACHE_SIZE_LIMIT = 10000
_users_snapshot = OrderedDict()

async def get_user_cached(user_id: int, platform: str) -> dict | None:
    """
    Get user data from LRU cache. If over limit, oldest items are dropped.
    """
    key = (user_id, platform)
    
    # 1. Cache HIT
    if key in _users_snapshot:
        _users_snapshot.move_to_end(key) # Mark as recently used
        return _users_snapshot[key]
    
    # 2. Cache MISS
    user = await storage.get_user(user_id, platform)
    if user:
        _users_snapshot[key] = user
        _users_snapshot.move_to_end(key)
        
        # Prune if over limit
        if len(_users_snapshot) > CACHE_SIZE_LIMIT:
            oldest_key, _ = _users_snapshot.popitem(last=False)
            logger.debug(f"LRU: Evicted user {oldest_key[0]} ({oldest_key[1]}) from cache.")
            
        logger.debug(f"User {user_id} ({platform}) cached in LRU snapshot (size={len(_users_snapshot)}).")
    return user

def invalidate_user_cache(user_id: int, platform: str):
    """Remove user from cache. Call this after set_user."""
    key = (user_id, platform)
    if key in _users_snapshot:
        del _users_snapshot[key]
        logger.debug(f"User {user_id} ({platform}) cache invalidated.")
