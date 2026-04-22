import asyncio
import logging
from aiogram.types import Message
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

async def schedule_deletion(message: Message, delay: int = 20):
    """Schedules a message for deletion after a specified delay.
    
    Safe for use in background tasks. Silently ignores errors (e.g. if bot 
    lacks delete permissions or message was already deleted).
    """
    if not message:
        return

    async def _delete():
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except TelegramAPIError:
            # Ignore permission errors or already deleted messages
            pass
        except Exception as e:
            logger.debug(f"Failed to delete message {message.message_id}: {e}")

    asyncio.create_task(_delete())
