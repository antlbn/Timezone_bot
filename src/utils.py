import asyncio
from functools import wraps
from aiogram.types import Message

from src.logger import get_logger
from src.config import get_settings_cleanup_timeout

logger = get_logger()

async def delete_message_after(message: Message, delay: int):
    """Sleep for delay seconds, then safely attempt to delete the message."""
    if delay <= 0:
        return
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Auto-cleanup: could not delete message {message.message_id} (already deleted or no permission).")

def auto_cleanup(delete_bot_msg: bool = True):
    """
    Decorator for command handlers to automatically delete the user's
    command phrase (like /tb_help) and the bot's response after a timeout.
    
    The wrapped handler MUST return the bot's reply Message object
    if `delete_bot_msg` is True.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            # Execute the handler and optionally capture its response message
            bot_msg = await func(message, *args, **kwargs)
            
            timeout = get_settings_cleanup_timeout()
            if timeout > 0:
                # 1. Delete user's command message
                asyncio.create_task(delete_message_after(message, timeout))
                
                # 2. Delete the bot's response message if configured and returned
                if delete_bot_msg and bot_msg and hasattr(bot_msg, "delete"):
                    asyncio.create_task(delete_message_after(bot_msg, timeout))
                    
            return bot_msg
        return wrapper
    return decorator
