"""
Discord Event Handlers — message monitoring and member tracking.
"""

import discord

from src.discord import bot
from src.storage import storage
from src.storage.user_cache import get_user_cached
from src.storage.pending import save_pending_message
from src.logger import get_logger
from src.event_detection import process_message

logger = get_logger()
PLATFORM = "discord"


def register_events(bot):
    """Explicitly trigger event registration."""
    # The decorators already register them to the bot instance,
    # but we call this to ensure the module is loaded.
    pass


@bot.event
async def on_message(message: discord.Message):
    """Handle messages — onboard new users, run LLM detection for registered ones."""
    if message.author.bot:
        return
    if not message.guild:
        return

    sender = await get_user_cached(message.author.id, platform=PLATFORM)
    timestamp_utc = message.created_at.isoformat() + "Z" if message.created_at else ""
    user_name = message.author.display_name or "User"
    chat_id = str(message.guild.id)

    # 1. Update activity timestamp (for all active users)
    await storage.update_activity(message.author.id, PLATFORM)

    # 2. Build send_fn so tools.py can reply to this channel
    async def send_fn(text: str) -> None:
        embed = discord.Embed(
            description=text,
            color=discord.Color.blue(),
        )
        await message.reply(embed=embed)

    # 3. Check registration status
    is_registered = bool(sender and sender.get("timezone"))

    # 4. LLM pipeline — detection + tool dispatch
    result = await process_message(
        message_text=message.content,
        chat_id=chat_id,
        user_id=str(message.author.id),
        platform=PLATFORM,
        author_name=user_name,
        timestamp_utc=timestamp_utc,
        sender_db=sender,
        send_fn=send_fn if is_registered else None,
    )

    logger.info(
        f"[guild:{chat_id}] LLM result for {user_name}: event={result.get('event')} "
        f"points={len(result.get('points', []))}"
    )

    # 5. Lazy Onboarding Trigger
    if not is_registered and result.get("event"):
        from src.discord.ui import SetTimezoneView
        from src.config import get_settings_cleanup_timeout

        embed = discord.Embed(
            title="👋 Welcome to Timezone Bot!",
            description=(
                f"Hi {user_name}! I've detected a time mention, but I don't know your timezone yet.\n\n"
                "Tap the button below to quickly set it up! (Only you will see the next steps)"
            ),
            color=discord.Color.gold(),
        )

        invite_msg = await message.reply(
            embed=embed,
            view=SetTimezoneView(message.author.id),
            mention_author=True,
            delete_after=get_settings_cleanup_timeout() or 60,
        )

        # 5.1 Save to In-Memory storage for later processing (Frozen)
        msg_data = {
            "platform": PLATFORM,
            "chat_id": chat_id,
            "channel_id": str(message.channel.id),
            "author_id": str(message.author.id),
            "author_name": user_name,
            "text": message.content,
            "timestamp_utc": timestamp_utc,
            "message_id": message.id,
        }
        await save_pending_message(message.author.id, PLATFORM, msg_data)

@bot.event
async def on_member_remove(member: discord.Member):
    """Remove user from storage when they leave the guild."""
    await storage.remove_chat_member(member.guild.id, member.id, platform=PLATFORM)
    logger.info(
        f"[guild:{member.guild.id}] Member {member.id} left, removed from storage"
    )


@bot.event
async def on_guild_remove(guild: discord.Guild):
    """Remove all members from research when bot is kicked from guild."""
    await storage.clear_chat_members(guild.id, platform=PLATFORM)
    logger.info(
        f"[guild:{guild.id}] Bot removed from guild, cleared all members from storage"
    )
