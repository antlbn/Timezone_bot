from aiogram.types import Message
from src.core.domain.value_objects import InputData, MessageContext
from src.core.domain.enums import Platform
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.container import AppContainer

logger = logging.getLogger(__name__)

async def on_message(message: Message, container: 'AppContainer') -> None:
    sender = await container.storage.get_user(message.from_user.id, Platform.TELEGRAM)
    
    ctx = MessageContext(input=InputData(
        text=message.text or "",
        user_id=message.from_user.id,
        platform=Platform.TELEGRAM,
        author_name=message.from_user.full_name,
        timestamp_utc=message.date,
        chat_id=str(message.chat.id),
        sender=sender,
        is_bot=message.from_user.is_bot
    ))
    
    ctx = await container.pipeline.run(ctx)
    commands = ctx.commands
    
    # Needs TelegramCtx from telegram_executor
    from src.adapters.executors.telegram_executor import TelegramCtx
    tg_ctx = TelegramCtx(message)
    await container.tg_executor.execute(commands, tg_ctx)
