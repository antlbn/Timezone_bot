"""
Discord Event Handlers - message monitoring and member tracking.
"""
import discord

from src.discord import bot
from src.storage import storage
from src import formatter
from src.logger import get_logger
from src.event_detection import process_message

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
        
    sender = await storage.get_user(message.author.id, platform=PLATFORM)
    timestamp_utc = message.created_at.isoformat() + "Z" if message.created_at else ""
    user_name = message.author.display_name or "User"
    
    if not sender or not sender.get("timezone"):
        # User not registered - prompt with button immediately
        # We do not extract time here, onboarding takes priority over any potential time mention.
        from src.discord.ui import SetTimezoneView
        await message.reply(
            f"{message.author.display_name}, set your timezone to convert times!",
            view=SetTimezoneView(message.author.id),
            mention_author=True
        )
        
        # Append message to deque for future context (without calling LLM evaluation)
        from src.event_detection.history import append_to_history
        append_to_history(
            platform=PLATFORM,
            chat_id=str(message.guild.id),
            message_data={
                "platform": PLATFORM,
                "chat_id": str(message.guild.id),
                "author_id": str(message.author.id),
                "author_name": user_name,
                "text": message.content,
                "timestamp_utc": timestamp_utc
            }
        )
        return
        
    # User is registered, pass message to the LLM Event Detection pipeline
    result = await process_message(
        message_text=message.content,
        chat_id=str(message.guild.id),
        user_id=str(message.author.id),
        platform=PLATFORM,
        author_name=user_name,
        timestamp_utc=timestamp_utc
    )
    
    if not result.get("trigger", False) or not result.get("times"):
        return
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
    
    # Determine the Source TZ (event_location override or sender DB fallback)
    event_location = result.get("event_location")
    if event_location:
        from src.geo import get_timezone_by_city
        geo_result = get_timezone_by_city(event_location)
        if geo_result and not geo_result.get("error"):
            source_city = geo_result["city"]
            source_tz = geo_result["timezone"]
            source_flag = geo_result["flag"]
        else:
            logger.warning(f"Failed to geocode event_location '{event_location}'. Falling back to sender TZ.")
            source_city = sender["city"]
            source_tz = sender["timezone"]
            source_flag = sender.get("flag", "")
    else:
        source_city = sender["city"]
        source_tz = sender["timezone"]
        source_flag = sender.get("flag", "")
        
    times = result.get("times", [])
    for time_str in times:
        reply = formatter.format_conversion_reply(
            time_str,
            source_city,
            source_tz,
            source_flag,
            active_members,
            user_name
        )
        await message.reply(reply)
    
    logger.info(f"[guild:{message.guild.id}] LLM Trigger: {times} | location_override={event_location}")


@bot.event
async def on_member_remove(member: discord.Member):
    """Remove user from storage when they leave the guild."""
    await storage.remove_chat_member(member.guild.id, member.id, platform=PLATFORM)
    logger.info(f"[guild:{member.guild.id}] Member {member.id} left, removed from storage")
