import discord
from core.domain.value_objects import InputData
from core.domain.enums import Platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import AppContainer

async def on_message(message: discord.Message, container: 'AppContainer') -> None:
    if message.author.bot or not message.guild:
        return

    data = InputData(
        text=message.content,
        user_id=message.author.id,
        platform=Platform.DISCORD,
        author_name=message.author.display_name,
        timestamp_utc=message.created_at,
        chat_id=str(message.guild.id),
        thread_id=str(message.channel.id),
        is_bot=message.author.bot
    )
    
    await container.message_processor.process_input(data)
