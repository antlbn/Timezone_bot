import discord
from src.core.domain.value_objects import InputData, MessageContext
from src.core.domain.enums import Platform
from src.core.pipeline.command_factory import create_commands
from src.adapters.executors.discord_executor import DiscordCtx

async def on_message(message: discord.Message, container) -> None:
    if message.author.bot or not message.guild:
        return

    sender = await container.storage.get_user(message.author.id, Platform.DISCORD)
    
    ctx = MessageContext(input=InputData(
        text=message.content,
        user_id=message.author.id,
        platform=Platform.DISCORD,
        author_name=message.author.display_name,
        timestamp_utc=message.created_at,
        chat_id=str(message.guild.id),
        sender=sender,
        is_bot=message.author.bot
    ))
    
    ctx = await container.pipeline.run(ctx)
    commands = create_commands(ctx)
    
    dc_ctx = DiscordCtx(message)
    await container.dc_executor.execute(commands, dc_ctx)
