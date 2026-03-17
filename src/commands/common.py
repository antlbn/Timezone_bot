from time import time

from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated, ForceReply, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_NOT_MEMBER
from aiogram.fsm.context import FSMContext

from src.storage import storage
from src.storage.user_cache import get_user_cached, invalidate_user_cache
from src.storage.pending import save_pending_message, get_and_delete_pending_messages
from src.config import get_bot_settings
from src.logger import get_logger
from src.commands.states import SetTimezone
from src.event_detection import process_message
from src.event_detection.history import append_to_history
from src.utils import auto_cleanup

router = Router()
logger = get_logger()

# Cooldown tracking: {chat_id: last_reply_timestamp}
_last_reply: dict[int, float] = {}


@router.message(Command("tb_help"))
@auto_cleanup(delete_bot_msg=True)
async def cmd_help(message: Message):
    """Show help menu."""
    help_text = (
        "Timezone Bot\n"
        "/tb_help - this help\n"
        "/tb_me    - your location\n"
        "/tb_settz - set city\n"
        "/tb_members - chat members\n"
        "/tb_remove - remove member\n\n"
        "Mention time (14:00) and I'll convert it!"
    )
    return await message.reply(help_text)


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

        # Check if we already have pending messages to avoid duplicate button prompts
        existing_pending = await get_and_delete_pending_messages(user_id, "telegram")
        
        if not existing_pending:
            # First time seeing this user (or previous session expired)
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📍 Set city", callback_data=f"onboarding:set:{user_id}"),
                InlineKeyboardButton(text="✖️ No thanks", callback_data=f"onboarding:decline:{user_id}")
            ]])
            
            welcome_text = (
                f"Hi {user_name}! I can help coordinate times in this chat. "
                "To show your local time to others, I need to know your city."
            )
            await message.reply(welcome_text, reply_markup=kb)
            
            # Put back the messages if they were fresh (save_pending_message handles fresh check)
            await save_pending_message(user_id, "telegram", msg_data)
        else:
            # Already pending, just add this one to the queue
            # (re-save all to maintain order and expiration)
            for m in existing_pending:
                await save_pending_message(user_id, "telegram", m)
            await save_pending_message(user_id, "telegram", msg_data)
        
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
