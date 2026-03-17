from aiogram import Router, F
from aiogram.types import Message, ForceReply, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.storage import storage
from src.storage.user_cache import get_user_cached, invalidate_user_cache
from src.storage.pending import get_and_delete_pending_messages, peek_pending_messages
from src.event_detection.history import append_to_history
from src.event_detection import process_message
from src import geo, formatter
from src.logger import get_logger
from src.commands.states import SetTimezone
from src.utils import auto_cleanup

router = Router()
logger = get_logger()

@router.message(Command("tb_me"))
@auto_cleanup(delete_bot_msg=True)
async def cmd_me(message: Message):
    """Show user's current timezone."""
    existing_user = await get_user_cached(message.from_user.id, platform="telegram")
    
    if not existing_user:
        return await message.reply("Not set. Use /tb_settz")
    
    return await message.reply(f"{existing_user['city']} {existing_user['flag']} ({existing_user['timezone']})")


@router.message(Command("tb_settz"))
@auto_cleanup(delete_bot_msg=True)
async def cmd_settz(message: Message, state: FSMContext):
    """Start timezone setting flow."""
    await state.update_data(user_id=message.from_user.id)
    await state.set_state(SetTimezone.waiting_for_city)
    return await message.reply("What city are you in?", reply_markup=ForceReply(selective=True))


@router.callback_query(F.data.startswith("onboarding:"))
async def process_onboarding_callback(callback: CallbackQuery, state: FSMContext):
    """Handle choice between setting timezone or declining."""
    parts = callback.data.split(":")
    action = parts[1]
    user_id = int(parts[2]) if len(parts) > 2 else None
    
    clicking_user_id = callback.from_user.id
    
    if user_id and clicking_user_id != user_id:
        await callback.answer("This button is not for you! 😊", show_alert=True)
        return

    chat_id = callback.message.chat.id
    user_name = callback.from_user.first_name or "User"
    
    if action == "decline":
        # Save as declined
        await storage.set_user(
            user_id=user_id,
            platform="telegram",
            city=None,
            timezone=None,
            username=callback.from_user.username or "",
            onboarding_declined=True
        )
        invalidate_user_cache(user_id, platform="telegram")
        
        # Delete the onboarding prompt to keep chat clean
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete onboarding message: {e}")
        
        # Process pending messages immediately (LLM will handle missing TZ)
        await _process_pending_queue(callback.message, user_id, user_name)
        
    elif action == "set":
        # Start city flow
        await state.update_data(user_id=user_id)
        await state.set_state(SetTimezone.waiting_for_city)
        
        # Try to find the latest message from user to reply to it (for better ForceReply activation)
        pending = await peek_pending_messages(user_id, "telegram")
        reply_to_id = pending[-1]["message_id"] if pending else callback.message.message_id
        
        # Delete the inline buttons message to keep chat clean
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete onboarding inline message: {e}")
            
        prompt_msg = await callback.message.bot.send_message(
            chat_id=chat_id,
            text=f"Great {user_name}! What city are you in?",
            reply_to_message_id=reply_to_id,
            reply_markup=ForceReply(selective=True)
        )
        await state.update_data(prompt_message_id=prompt_msg.message_id)
        await callback.answer()


@router.message(SetTimezone.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    """Process city name input - only from the user who initiated, must be reply."""
    data = await state.get_data()
    
    if data.get("user_id") != message.from_user.id:
        return
    
    
    # We no longer strictly require a reply to the bot's message to be more user-friendly.
    
    # Clean up the user's input and the bot's prompt
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete user's message: {e}")
        
    try:
        if data.get("prompt_message_id"):
            await message.bot.delete_message(chat_id=message.chat.id, message_id=data["prompt_message_id"])
    except Exception as e:
        logger.warning(f"Failed to delete bot's prompt: {e}")
    
    city_name = message.text.strip()
    location = geo.get_timezone_by_city(city_name)
    
    if not location or "error" in location:
        if location and "error" in location:
            logger.warning(f"Geo error: {location['error']}")
            
        # Trigger fallback: ask for time or city retry
        await state.set_state(SetTimezone.waiting_for_time)
        prompt_msg = await message.answer(
            f"Could not find '{city_name}' (or service error).\n"
            "Enter your current time (e.g. 14:30) or try another city:",
            reply_markup=ForceReply(selective=True)
        )
        await state.update_data(prompt_message_id=prompt_msg.message_id)
        return
    
    await _save_and_finish(message, state, location)


@router.message(SetTimezone.waiting_for_time)
async def process_fallback_input(message: Message, state: FSMContext):
    """Process user's input for fallback - can be time OR city retry."""
    data = await state.get_data()
    
    if data.get("user_id") != message.from_user.id:
        return
    
    # Relaxing reply check here too for better UX
    
    # Clean up the user's input and the bot's prompt
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete user's message: {e}")
        
    try:
        if data.get("prompt_message_id"):
            await message.bot.delete_message(chat_id=message.chat.id, message_id=data["prompt_message_id"])
    except Exception as e:
        logger.warning(f"Failed to delete bot's prompt: {e}")
    
    user_input = (message.text or "").strip()
    
    # Use unified resolver
    location = geo.resolve_timezone_from_input(user_input)
    
    if location:
        await _save_and_finish(message, state, location, is_retry=True)
        return
    
    # Neither city nor time - ask again
    prompt_msg = await message.answer(
        f"Could not find '{user_input}'.\n"
        "Enter your current time (e.g. 14:30) or try another city:",
        reply_markup=ForceReply(selective=True)
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
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
    invalidate_user_cache(message.from_user.id, platform="telegram")
    
    if message.chat.id != message.from_user.id:
        await storage.add_chat_member(message.chat.id, message.from_user.id, platform="telegram")
    
    await state.clear()
    
    await message.answer(f"Set {user_name}: {location['city']} {location['flag']} ({location['timezone']})")
    
    # Process all pending messages
    await _process_pending_queue(message, message.from_user.id, user_name)

    log_suffix = " (retry)" if is_retry else ""
    logger.info(f"[chat:{message.chat.id}] User {message.from_user.id} -> {location['timezone']}{log_suffix}")


async def _process_pending_queue(message: Message, user_id: int, user_name: str):
    """Helper to drain the pending queue for a user."""
    pending_list = await get_and_delete_pending_messages(user_id, "telegram")
    if not pending_list:
        return

    logger.info(f"[chat:{message.chat.id}] Draining {len(pending_list)} pending messages for user {user_id}")
    
    # We re-fetch user record from CACHE
    user_record = await get_user_cached(user_id, platform="telegram")

    for pending in pending_list:
        # Build send_fn for each message
        async def send_reply_fn(text: str) -> None:
            await message.bot.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_to_message_id=pending.get("message_id")
            )
            
        # Add to history for context (since we skipped it in common)
        snapshot = append_to_history("telegram", str(message.chat.id), pending)

        await process_message(
            message_text=pending["text"],
            chat_id=str(message.chat.id),
            user_id=str(user_id),
            platform="telegram",
            author_name=pending["author_name"],
            timestamp_utc=pending["timestamp_utc"],
            sender_db=user_record,
            send_fn=send_reply_fn,
            skip_history_append=True,
            precomputed_snapshot=snapshot
        )
