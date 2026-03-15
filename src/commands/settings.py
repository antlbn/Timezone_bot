from aiogram import Router
from aiogram.types import Message, ForceReply
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.storage import storage
from src import geo, formatter
from src.logger import get_logger
from src.commands.states import SetTimezone

router = Router()
logger = get_logger()

@router.message(Command("tb_me"))
async def cmd_me(message: Message):
    """Show user's current timezone."""
    existing_user = await storage.get_user(message.from_user.id, platform="telegram")
    
    if not existing_user:
        await message.reply("Not set. Use /tb_settz")
        return
    
    await message.reply(f"{existing_user['city']} {existing_user['flag']} ({existing_user['timezone']})")


@router.message(Command("tb_settz"))
async def cmd_settz(message: Message, state: FSMContext):
    """Start timezone setting flow."""
    await state.update_data(user_id=message.from_user.id)
    await state.set_state(SetTimezone.waiting_for_city)
    await message.reply("What city are you in?", reply_markup=ForceReply(selective=True))


@router.message(SetTimezone.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    """Process city name input - only from the user who initiated, must be reply."""
    data = await state.get_data()
    
    if data.get("user_id") != message.from_user.id:
        await state.clear()
        return
    
    if not message.reply_to_message or message.reply_to_message.from_user.is_bot is False:
        await state.clear()
        return
    
    city_name = message.text.strip()
    location = geo.get_timezone_by_city(city_name)
    
    if not location or "error" in location:
        if location and "error" in location:
            logger.warning(f"Geo error: {location['error']}")
            
        # Trigger fallback: ask for time or city retry
        await state.set_state(SetTimezone.waiting_for_time)
        await message.reply(
            f"Could not find '{city_name}' (or service error).\n"
            "Enter your current time (e.g. 14:30) or try another city:",
            reply_markup=ForceReply(selective=True)
        )
        return
    
    await _save_and_finish(message, state, location)


@router.message(SetTimezone.waiting_for_time)
async def process_fallback_input(message: Message, state: FSMContext):
    """Process user's input for fallback - can be time OR city retry."""
    data = await state.get_data()
    
    if data.get("user_id") != message.from_user.id:
        await state.clear()
        return
    
    if not message.reply_to_message or message.reply_to_message.from_user.is_bot is False:
        await state.clear()
        return
    
    user_input = (message.text or "").strip()
    
    # Use unified resolver
    location = geo.resolve_timezone_from_input(user_input)
    
    if location:
        await _save_and_finish(message, state, location, is_retry=True)
        return
    
    # Neither city nor time - ask again
    await message.reply(
        f"Could not find '{user_input}'.\n"
        "Enter your current time (e.g. 14:30) or try another city:",
        reply_markup=ForceReply(selective=True)
    )
    # Stay in waiting_for_time state for retry


async def _save_and_finish(
    message: Message, 
    state: FSMContext, 
    location: dict, 
    is_retry: bool = False
):
    """Helper to save user data, update state, and send confirmation."""
    username = message.from_user.username or ""
    user_name = message.from_user.first_name or "User"
    
    await storage.set_user(
        user_id=message.from_user.id,
        platform="telegram",
        city=location["city"],
        timezone=location["timezone"],
        flag=location["flag"],
        username=username
    )
    
    if message.chat.id != message.from_user.id:
        await storage.add_chat_member(message.chat.id, message.from_user.id, platform="telegram")
    
    await state.clear()
    
    await message.answer(f"Set {user_name}: {location['city']} {location['flag']} ({location['timezone']})")
    
    # 2. Check for and process pending message
    from src.storage.pending import get_and_delete_pending_message
    pending = await get_and_delete_pending_message(message.from_user.id, "telegram")
    
    if pending:
        logger.info(f"[chat:{message.chat.id}] Processing pending message for user {message.from_user.id}")
        from src.event_detection import process_message
        
        # Build send_fn that replies to the original message
        async def send_reply_fn(text: str) -> None:
            await message.bot.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_to_message_id=pending.get("message_id")
            )
            
        # We re-fetch user record to be sure (though we have location here)
        # But process_message expects a sender_db dict
        user_record = await storage.get_user(message.from_user.id, platform="telegram")
        
        await process_message(
            message_text=pending["text"],
            chat_id=str(message.chat.id),
            user_id=str(message.from_user.id),
            platform="telegram",
            author_name=pending["author_name"],
            timestamp_utc=pending["timestamp_utc"],
            sender_db=user_record,
            send_fn=send_reply_fn,
            skip_history_append=True,
            precomputed_snapshot=pending.get("snapshot")
        )

    log_suffix = " (retry)" if is_retry else ""
    logger.info(f"[chat:{message.chat.id}] User {message.from_user.id} -> {location['timezone']}{log_suffix}")
