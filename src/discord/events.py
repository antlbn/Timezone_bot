"""
Discord Event Handlers - message monitoring and member tracking.
"""
import discord

from src.discord import bot
from src.storage import storage
from src import capture, formatter
from src.logger import get_logger

logger = get_logger()
PLATFORM = "discord"


@bot.event
async def on_message(message: discord.Message):
    """Handle messages - detect time mentions and convert."""
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Only in guilds
    if not message.guild:
        return
    
    # Check for time patterns
    times = capture.extract_times(message.content)
    if not times:
        return
    
    sender = await storage.get_user(message.author.id, platform=PLATFORM)
    
    if not sender or not sender.get("timezone"):
        # User not registered - prompt to use /tb_settz
        await message.reply(
            f"{message.author.display_name}, set your timezone first: `/tb_settz`",
            mention_author=True
        )
        return
    
    # Get guild members
    members = await storage.get_chat_members(message.guild.id, platform=PLATFORM)
    if not members:
        return
    
    sender_flag = sender.get("flag", "")
    user_name = message.author.display_name or "User"
    
    for time_str in times:
        reply = formatter.format_conversion_reply(
            time_str,
            sender["city"],
            sender["timezone"],
            sender_flag,
            members,
            user_name
        )
        await message.reply(reply)
    
    logger.info(f"[guild:{message.guild.id}] Times: {times}")


@bot.event
async def on_member_remove(member: discord.Member):
    """Remove user from storage when they leave the guild."""
    await storage.remove_chat_member(member.guild.id, member.id, platform=PLATFORM)
    logger.info(f"[guild:{member.guild.id}] Member {member.id} left, removed from storage")
