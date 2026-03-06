from time import time

from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated, ForceReply
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_NOT_MEMBER
from aiogram.fsm.context import FSMContext

from src.storage import storage
from src import formatter
from src.config import get_bot_settings
from src.logger import get_logger
from src.commands.states import SetTimezone
from src.event_detection import process_message

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
    """Handle regular messages - new user onboarding and LLM event detection."""
    if not message.text:
        return
        
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name or "User"
    timestamp_utc = message.date.isoformat() + "Z" if message.date else ""
    
    sender = await storage.get_user(user_id, platform="telegram")
    
    # 1. Immediate Onboarding Flow
    if not sender or not sender.get("timezone"):
        if sender and not sender.get("timezone"):
             logger.error(f"User {user_id} has no timezone data")

        # Just save the user's ID to state, do not bother saving pending time
        await state.update_data(user_id=user_id)
        await state.set_state(SetTimezone.waiting_for_city)
        await message.reply(f"{user_name}, what city are you in?", reply_markup=ForceReply(selective=True))
        
        # We process the message text via the LLM pipeline just to add it to the history deque. 
        # But we intentionally ignore the LLM evaluation result since onboarding takes priority.
        # Actually, adding it to the deque without LLM evaluation is better for MVP.
        from src.event_detection.history import append_to_history
        append_to_history(
            platform="telegram",
            chat_id=str(chat_id),
            message_data={
                "platform": "telegram",
                "chat_id": str(chat_id),
                "author_id": str(user_id),
                "author_name": user_name,
                "text": message.text,
                "timestamp_utc": timestamp_utc
            }
        )
        return
        
    # 2. LLM Event Detection
    result = await process_message(
        message_text=message.text,
        chat_id=str(chat_id),
        user_id=str(user_id),
        platform="telegram",
        author_name=user_name,
        timestamp_utc=timestamp_utc
    )
    
    if not result.get("trigger", False) or not result.get("times"):
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
            members,
            user_name
        )
        await message.answer(reply)
    
    logger.info(f"[chat:{chat_id}] LLM Trigger: {times} | location_override={event_location}")


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER))
async def on_bot_kicked(event: ChatMemberUpdated):
    """Clean up chat members when bot is kicked."""
    await storage.clear_chat_members(event.chat.id, platform="telegram")
    logger.info(f"[chat:{event.chat.id}] Bot kicked, cleared chat members")
