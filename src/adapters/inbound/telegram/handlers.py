from aiogram.types import Message
from src.core.domain.value_objects import InputData, MessageContext
from src.core.domain.enums import Platform
from src.adapters.executors.telegram_executor import TelegramCtx
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.main import AppContainer

logger = logging.getLogger(__name__)

async def on_message(message: Message, container: 'AppContainer') -> None:
    ctx = MessageContext(input=InputData(
        text=message.text or "",
        user_id=message.from_user.id,
        platform=Platform.TELEGRAM,
        author_name=message.from_user.full_name,
        timestamp_utc=message.date,
        chat_id=str(message.chat.id),
        is_bot=message.from_user.is_bot
    ))
    
    ctx = await container.pipeline.run(ctx)
    commands = ctx.commands
    if not commands:
        return
    
    # Needs TelegramCtx from telegram_executor
    tg_ctx = TelegramCtx(message)
    await container.tg_executor.execute(commands, tg_ctx)
