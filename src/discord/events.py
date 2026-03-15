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
from src.event_detection.history import append_to_history

logger = get_logger()
PLATFORM = "discord"


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

    # 1. Onboarding — sender not registered yet
    if not sender or not sender.get("timezone"):
        from src.discord.ui import SetTimezoneView
        await message.reply(
            f"{user_name}, set your timezone to convert times!",
            view=SetTimezoneView(message.author.id),
            mention_author=True,
        )

        # 1.1 Snapshot N preceding messages, then append current message to deque
        msg_data = {
            "platform":      PLATFORM,
            "chat_id":       chat_id,
            "author_id":     str(message.author.id),
            "author_name":   user_name,
            "text":          message.content,
            "timestamp_utc": timestamp_utc,
            "message_id":    message.id,
        }
        snapshot = append_to_history(PLATFORM, chat_id, msg_data)

        # 1.2 Save to In-Memory storage for later processing
        await save_pending_message(message.author.id, PLATFORM, {
            **msg_data,
            "snapshot": snapshot
        })
        return

    # 2. Active-member filter — prune stale DB members while we're here
    db_members = await storage.get_chat_members(message.guild.id, platform=PLATFORM)
    for m in list(db_members):
        if not message.guild.get_member(m["user_id"]):
            await storage.remove_chat_member(message.guild.id, m["user_id"], platform=PLATFORM)
            logger.info(f"[guild:{chat_id}] Auto-removed stale user {m['user_id']}")

    # 3. Build send_fn so tools.py can reply to this channel
    async def send_fn(text: str) -> None:
        await message.reply(text)

    # 4. LLM pipeline — detection + tool dispatch happen inside process_message
    result = await process_message(
        message_text=message.content,
        chat_id=chat_id,
        user_id=str(message.author.id),
        platform=PLATFORM,
        author_name=user_name,
        timestamp_utc=timestamp_utc,
        sender_db=sender,
        send_fn=send_fn,
    )

    logger.info(
        f"[guild:{chat_id}] LLM result: event={result.get('event')} "
        f"times={result.get('time')} cities={result.get('city')}"
    )


@bot.event
async def on_member_remove(member: discord.Member):
    """Remove user from storage when they leave the guild."""
    await storage.remove_chat_member(member.guild.id, member.id, platform=PLATFORM)
    logger.info(f"[guild:{member.guild.id}] Member {member.id} left, removed from storage")
