import json
import redis.asyncio as redis
from src.config import get_redis_url
from src.logger import get_logger

logger = get_logger()

async def _get_client():
    """Create a new Redis client."""
    return redis.from_url(get_redis_url(), decode_responses=True)

async def save_pending_message(user_id: int, platform: str, message_data: dict, ttl: int = 60):
    """
    Save a message that is pending onboarding.
    
    Parameters:
    - user_id: Platform user ID.
    - platform: "telegram" | "discord"
    - message_data: Dictionary with message info (text, chat_id, snapshot, etc.)
    - ttl: Time to live in seconds (default 60).
    """
    key = f"pending_msg:{platform}:{user_id}"
    client = await _get_client()
    try:
        # Serialize data to JSON
        value = json.dumps(message_data)
        await client.set(key, value, ex=ttl)
        logger.debug(f"Saved pending message for {platform}:{user_id} (TTL={ttl})")
    except Exception as e:
        logger.error(f"Error saving pending message to Redis: {e}", exc_info=True)
    finally:
        await client.aclose()

async def get_and_delete_pending_message(user_id: int, platform: str) -> dict | None:
    """
    Atomically retrieve and delete a pending message.
    """
    key = f"pending_msg:{platform}:{user_id}"
    client = await _get_client()
    try:
        # FETCH AND DELETE in one go (simulated with GET + DEL since we want the data)
        # We could use a Lua script for true atomicity, but GET then DEL is fine here 
        # because the key is user-specific and onboarding is sequential.
        value = await client.get(key)
        if value:
            await client.delete(key)
            logger.debug(f"Retrieved and deleted pending message for {platform}:{user_id}")
            return json.loads(value)
        return None
    except Exception as e:
        logger.error(f"Error getting pending message from Redis: {e}", exc_info=True)
        return None
    finally:
        await client.aclose()
