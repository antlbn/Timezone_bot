import asyncio
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
    except Exception:
        logger.debug(
            f"Auto-cleanup: could not delete message {message.message_id} (already deleted or no permission)."
        )


def auto_cleanup(delete_bot_msg: bool = True, keep_bot_msg_in_dm: bool = False):
    """
    Decorator for command handlers to automatically delete the user's
    command phrase (like /tb_help) and the bot's response after a timeout.
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            bot_msg = await func(message, *args, **kwargs)
            timeout = get_settings_cleanup_timeout()
            if timeout > 0:
                asyncio.create_task(delete_message_after(message, timeout))
                is_dm = message.chat.type == "private"
                should_delete_bot = delete_bot_msg
                if is_dm and keep_bot_msg_in_dm:
                    should_delete_bot = False
                if should_delete_bot and bot_msg and hasattr(bot_msg, "delete"):
                    asyncio.create_task(delete_message_after(bot_msg, timeout))
            return bot_msg

        return wrapper

    return decorator
