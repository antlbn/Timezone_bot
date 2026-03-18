import asyncio
from time import time

from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_NOT_MEMBER
from aiogram.fsm.context import FSMContext
from aiogram.utils.deep_linking import create_start_link

from src.storage import storage
from src.storage.user_cache import get_user_cached, invalidate_user_cache
from src.storage.pending import (
    save_pending_message, get_and_delete_pending_messages,
    should_send_dm_invite, mark_dm_invite_sent,
)
from src.config import get_bot_settings, get_dm_onboarding_cooldown, get_settings_cleanup_timeout
from src.logger import get_logger
from src.commands.states import SetTimezone
from src.event_detection import process_message
from src.event_detection.history import append_to_history
from src.utils import auto_cleanup, delete_message_after

router = Router()
logger = get_logger()

# Cooldown tracking: {chat_id: last_reply_timestamp}
_last_reply: dict[int, float] = {}


@router.message(Command("tb_help"))
@auto_cleanup(delete_bot_msg=True, keep_bot_msg_in_dm=True)
async def cmd_help(message: Message):
    """Show help menu (context-aware: group vs DM)."""
    is_dm = message.chat.type == "private"
    chat_title = message.chat.title or "this chat"
    
    if is_dm:
        help_text = (
            "🤖 *Timezone Bot Help*\n"
            "\n"
            "*Personal Commands (work anywhere):*\n"
            "• `/tb_me` — Show your current location\n"
            "• `/tb_settz` — Set or change your city/timezone\n"
            "\n"
            "*Chat Management (work in groups):*\n"
            "• `/tb_members` — List tracked members\n"
            "• `/tb_remove` — Manually remove a member from the list\n"
            "\n"
            "Just mention a time (e.g., `15:00` or `tomorrow at 3pm`) in any group where I am present, and I'll convert it for everyone!"
        )
        return await message.answer(help_text, parse_mode="Markdown")
    
    # In Group Chat
    link = await create_start_link(message.bot, "help")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚙️ Manage my settings", url=link)
    ]])
    
    help_text = (
        f"🤖 *Timezone Bot* in {chat_title}\n"
        "\n"
        "To set your personal timezone, please message me directly 👇\n"
        "\n"
        "*Chat Management:*\n"
        "• `/tb_members` — List tracked members\n"
        "• `/tb_remove`  — Remove a member manually\n"
        "\n"
        "I automatically convert times mentioned in the chat!"
    )
    return await message.reply(help_text, reply_markup=kb, parse_mode="Markdown")


@router.message(Command("tb_me"))
@auto_cleanup(delete_bot_msg=True, keep_bot_msg_in_dm=True)
async def cmd_me(message: Message):
    """Show user's current timezone setting."""
    user_id = message.from_user.id
    user_record = await get_user_cached(user_id, platform="telegram")
    
    if not user_record or not user_record.get("timezone"):
        return await message.reply("📍 You haven't set your timezone yet. Use /tb_settz to set it!")
    
    city = user_record.get("city")
    timezone = user_record.get("timezone")
    flag = user_record.get("flag", "")
    
    return await message.reply(f"📍 Your timezone is set to: *{city} {flag}* ({timezone})", parse_mode="Markdown")


@router.message(Command("tb_settz"))
@auto_cleanup(delete_bot_msg=True, keep_bot_msg_in_dm=False)
async def cmd_settz(message: Message, state: FSMContext):
    """Start timezone setting flow."""
    is_dm = message.chat.type == "private"
    
    if is_dm:
        # Re-use the DM onboarding/settings logic
        from src.commands.settings import dm_onboarding_start
        # We simulate a /start call but without arguments
        return await dm_onboarding_start(message, None, state)
    
    # In Group: Show JIT invite (or trigger the flow if we want, but JIT is preferred)
    # Actually, JIT invite is exactly what handle_time_mention does.
    # We can just manually trigger a fake time mention behavior or just send the link.
    link = await create_start_link(message.bot, f"onboard_{message.from_user.id}_{message.chat.id}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📍 Set my city", url=link)
    ]])
    
    return await message.reply(
        "To set your timezone, please tap the button below and I'll help you in DM! 👇",
        reply_markup=kb
    )


@router.message(F.text)
async def handle_time_mention(message: Message, state: FSMContext, skip_aging: bool = False):
    """Handle regular messages — onboarding for new users, LLM event detection for registered ones."""
    if not message.text:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name or "User"
    timestamp_utc = message.date.isoformat() + "Z" if message.date else ""

    sender = await get_user_cached(user_id, platform="telegram")

    # 1. Onboarding — sender not registered yet (and hasn't declined)
    if not sender or (not sender.get("timezone") and not sender.get("onboarding_declined")):
        msg_data = {
            "platform":      "telegram",
            "chat_id":       str(chat_id),
            "author_id":     str(user_id),
            "author_name":   user_name,
            "text":          message.text,
            "timestamp_utc": timestamp_utc,
            "message_id":    message.message_id,
        }

        # Always save this message to pending queue
        await save_pending_message(user_id, "telegram", msg_data)

        # Check cooldown — don't spam user if they recently ignored/abandoned an invite
        cooldown = get_dm_onboarding_cooldown()
        if not await should_send_dm_invite(user_id, "telegram", cooldown):
            logger.debug(f"[chat:{chat_id}] DM invite on cooldown for user {user_id}, skipping")
            return

        # Generate deep link to bot's DM with onboarding payload
        link = await create_start_link(message.bot, f"onboard_{user_id}_{chat_id}")
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📍 Set up timezone", url=link)
        ]])

        invite_msg = await message.reply(
            f"Hi {user_name}! Tap the button to quickly set up your timezone 👇",
            reply_markup=kb,
        )

        await mark_dm_invite_sent(user_id, "telegram")

        # Auto-cleanup the invite from the group chat
        cleanup_timeout = get_settings_cleanup_timeout()
        if cleanup_timeout > 0:
            asyncio.create_task(delete_message_after(invite_msg, cleanup_timeout))

        return

    # 2. Check cooldown before hitting the LLM
    cooldown = get_bot_settings().get("cooldown_seconds", 0)
    if cooldown > 0:
        now = time()
        if now - _last_reply.get(chat_id, 0) < cooldown:
            logger.debug(f"[chat:{chat_id}] Cooldown active, skipping LLM call")
            return
        _last_reply[chat_id] = now

    # 3. Update activity timestamp
    await storage.update_activity(message.from_user.id, "telegram")

    # 4. Build send_fn so tools.py can reply to this chat
    async def send_fn(text: str) -> None:
        await message.answer(text)

    # 5. LLM pipeline — detection + tool dispatch happen inside process_message
    result = await process_message(
        message_text=message.text,
        chat_id=str(chat_id),
        user_id=str(user_id),
        platform="telegram",
        author_name=user_name,
        timestamp_utc=timestamp_utc,
        sender_db=sender,
        send_fn=send_fn,
        skip_aging=skip_aging,
    )

    logger.info(
        f"[chat:{chat_id}] LLM result: event={result.get('event')} "
        f"times={result.get('time')} cities={result.get('city')}"
    )


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER))
async def on_bot_kicked(event: ChatMemberUpdated):
    """Clean up chat members when bot is kicked."""
    await storage.clear_chat_members(event.chat.id, platform="telegram")
    logger.info(f"[chat:{event.chat.id}] Bot kicked, cleared chat members")
