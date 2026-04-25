import discord
from core.domain.value_objects import InputData
from core.domain.enums import Platform
from core.services.message_processing import MessageProcessingService

async def on_message(message: discord.Message, message_processor: MessageProcessingService) -> None:
    if message.author.bot or not message.guild:
        return

    try:
        data = InputData(
            text=message.content,
            user_id=message.author.id,
            platform=Platform.DISCORD,
            author_name=message.author.display_name,
            timestamp_utc=message.created_at,
            chat_id=str(message.guild.id),
            thread_id=str(message.channel.id),
            is_bot=False
        )
        
        await message_processor.process_input(data)
    except Exception:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Discord on_message failed user=%s", message.author.id)

