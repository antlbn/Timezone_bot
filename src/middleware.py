"""
Middleware module.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from src import storage

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
                # Fire and forget - don't await result to avoid slowing down processing too much?
                # For SQLite it's fast enough to await.
                # Only if user is known (already has data)
                try:
                    user = await storage.get_user(event.from_user.id)
                    if user:
                        await storage.add_chat_member(event.chat.id, event.from_user.id)
                except Exception:
                    # Don't fail the update if storage fails
                    pass

        # Call next handler
        return await handler(event, data)
