from time import time

from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated, ForceReply
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_NOT_MEMBER
from aiogram.fsm.context import FSMContext

from src.storage import storage
from src import capture, formatter
from src.config import get_bot_settings
from src.logger import get_logger
from src.commands.states import SetTimezone

router = Router()
logger = get_logger()

# Cooldown tracking: {chat_id: last_reply_timestamp}
_last_reply: dict[int, float] = {}

@router.message(Command("tb_help"))
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
    await message.reply(help_text)


@router.message(F.text)
async def handle_time_mention(message: Message, state: FSMContext):
    """Handle regular messages - check for time mentions."""
    if not message.text:
        return
    
    times = capture.extract_times(message.text)
    if not times:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name or "User"
    
    sender = await storage.get_user(user_id, platform="telegram")
    
    if not sender or not sender.get("timezone"):
        if sender and not sender.get("timezone"):
             logger.error(f"User {user_id} has no timezone data")

        await state.update_data(user_id=user_id, pending_time=times[0])
        await state.set_state(SetTimezone.waiting_for_city)
        await message.reply(f"{user_name}, what city are you in?", reply_markup=ForceReply(selective=True))
        return
    
    # Check cooldown
    cooldown = get_bot_settings().get("cooldown_seconds", 0)
    if cooldown > 0:
        now = time()
        last = _last_reply.get(chat_id, 0)
        if now - last < cooldown:
            logger.debug(f"[chat:{chat_id}] Cooldown active, skipping reply")
            return
        _last_reply[chat_id] = now

    # Get chat members
    members = await storage.get_chat_members(chat_id, platform="telegram")
    if not members:
        return
    
    sender_flag = sender.get("flag", "")
    
    for time_str in times:
        reply = formatter.format_conversion_reply(
            time_str,
            sender["city"],
            sender["timezone"],
            sender_flag,
            members,
            user_name
        )
        await message.answer(reply)
    
    logger.info(f"[chat:{chat_id}] Times: {times}")


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER))
async def on_bot_kicked(event: ChatMemberUpdated):
    """Clean up chat members when bot is kicked."""
    await storage.clear_chat_members(event.chat.id, platform="telegram")
    logger.info(f"[chat:{event.chat.id}] Bot kicked, cleared chat members")
