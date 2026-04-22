import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from adapters.inbound.telegram import ui

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(BaseMiddleware):
    """
    Global error handler for Telegram adapter.
    Catches exceptions from handlers, logs them, and notifies the user.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            user_id = "unknown"
            if isinstance(event, (Message, CallbackQuery)) and event.from_user:
                user_id = event.from_user.id
            
            logger.exception(f"Error in Telegram handler for user {user_id}: {e}")
            
            # Notify user
            try:
                if isinstance(event, Message):
                    await event.answer(ui.get_error_message_text())
                elif isinstance(event, CallbackQuery):
                    await event.answer(ui.get_error_message_text(), show_alert=True)
            except Exception as notify_err:
                logger.error(f"Failed to send error notification to user {user_id}: {notify_err}")
            
            return None
