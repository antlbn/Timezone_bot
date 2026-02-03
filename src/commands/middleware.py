from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
from src.storage import storage
from src.logger import get_logger

logger = get_logger()

class PassiveCollectionMiddleware(BaseMiddleware):
    """
    Middleware to track known users in group chats.
    Runs for EVERY message without blocking other handlers.
    """
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Only process actual messages with users
        if isinstance(event, Message) and event.from_user:
            # Skip private chats
            if event.chat.id != event.from_user.id:
                try:
                    user = await storage.get_user(event.from_user.id, platform="telegram")
                    if user:
                        await storage.add_chat_member(event.chat.id, event.from_user.id, platform="telegram")
                except Exception as e:
                    logger.warning(f"Middleware storage error: {e}")
        
        return await handler(event, data)
