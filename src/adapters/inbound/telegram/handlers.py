from aiogram.types import Message
from core.domain.value_objects import InputData
from core.domain.enums import Platform
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import AppContainer

logger = logging.getLogger(__name__)

async def on_message(message: Message, container: 'AppContainer') -> None:
    data = InputData(
        text=message.text or "",
        user_id=message.from_user.id,
        platform=Platform.TELEGRAM,
        author_name=message.from_user.first_name,
        timestamp_utc=message.date,
        chat_id=str(message.chat.id),
        thread_id=str(message.message_thread_id) if message.message_thread_id else None,
        is_bot=message.from_user.is_bot
    )
    
    await container.message_processor.process_input(data)
