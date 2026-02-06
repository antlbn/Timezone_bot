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
        # User not registered - prompt with button
        from src.discord.commands import SetTimezoneView
        await message.reply(
            f"{message.author.display_name}, set your timezone to convert times!",
            view=SetTimezoneView(message.author.id),
            mention_author=True
        )
        return
    
    # Get guild members and auto-cleanup stale ones
    db_members = await storage.get_chat_members(message.guild.id, platform=PLATFORM)
    if not db_members:
        return
    
    # Filter: keep only members still in the guild, remove stale ones
    active_members = []
    for m in db_members:
        discord_member = message.guild.get_member(m["user_id"])
        if discord_member:
            active_members.append(m)
        else:
            # User left while bot was offline - cleanup
            await storage.remove_chat_member(message.guild.id, m["user_id"], platform=PLATFORM)
            logger.info(f"[guild:{message.guild.id}] Auto-removed stale user {m['user_id']}")
    
    if not active_members:
        return
    
    sender_flag = sender.get("flag", "")
    user_name = message.author.display_name or "User"
    
    for time_str in times:
        reply = formatter.format_conversion_reply(
            time_str,
            sender["city"],
            sender["timezone"],
            sender_flag,
            active_members,
            user_name
        )
        await message.reply(reply)
    
    logger.info(f"[guild:{message.guild.id}] Times: {times}")


@bot.event
async def on_member_remove(member: discord.Member):
    """Remove user from storage when they leave the guild."""
    await storage.remove_chat_member(member.guild.id, member.id, platform=PLATFORM)
    logger.info(f"[guild:{member.guild.id}] Member {member.id} left, removed from storage")
