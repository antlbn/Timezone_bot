from aiogram import Router, F
from aiogram.types import Message, ForceReply, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext

from src.storage import storage
from src.storage.user_cache import get_user_cached, invalidate_user_cache
from src.storage.pending import get_and_delete_pending_messages, clear_dm_invite
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


# ---------------------------------------------------------------------------
# DM Onboarding — Deep Link flow
# ---------------------------------------------------------------------------

@router.message(CommandStart(deep_link=True), F.chat.type == "private")
async def dm_onboarding_start(message: Message, command: CommandObject, state: FSMContext):
    """
    Handle deep link from group chat — start onboarding in DM.
    Payload format: onboard_{user_id}_{chat_id}
    """
    payload = command.args
    if not payload or not payload.startswith("onboard_"):
        return

    try:
        parts = payload.split("_")
        user_id = int(parts[1])
        chat_id = int(parts[2])
    except (IndexError, ValueError):
        logger.warning(f"Invalid onboarding deep link payload: {payload}")
        return

    # Security: only the target user can trigger their own onboarding
    if message.from_user.id != user_id:
        await message.answer("This link is not for you! 😊")
        return

    user_name = message.from_user.first_name or "User"

    # Check if user already has a timezone (e.g. they clicked an old link)
    existing = await get_user_cached(user_id, platform="telegram")
    if existing and existing.get("timezone"):
        await message.answer(
            f"You're already set up: {existing['city']} {existing['flag']} ({existing['timezone']})\n"
            "Use /tb_settz to change."
        )
        return

    # Show city prompt with decline option
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✖️ No thanks", callback_data=f"dm_decline:{user_id}:{chat_id}")
    ]])
    await message.answer(
        f"Hi {user_name}! What city are you in?",
        reply_markup=kb,
    )
    await state.set_state(SetTimezone.waiting_for_city)
    await state.update_data(user_id=user_id, source_chat_id=chat_id)


@router.callback_query(F.data.startswith("dm_decline:"))
async def dm_decline_callback(callback: CallbackQuery, state: FSMContext):
    """Handle 'No thanks' in DM."""
    parts = callback.data.split(":")
    try:
        user_id = int(parts[1])
        chat_id = int(parts[2])
    except (IndexError, ValueError):
        await callback.answer("Error processing request.")
        return

    clicking_user_id = callback.from_user.id
    if clicking_user_id != user_id:
        await callback.answer("This button is not for you! 😊", show_alert=True)
        return

    user_name = callback.from_user.first_name or "User"

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

    # Clear FSM state
    await state.clear()

    # Acknowledge in DM
    await callback.message.edit_text("Got it! If you change your mind, use /tb_settz in any chat.")
    await callback.answer()

    # Clear the DM invite cooldown
    await clear_dm_invite(user_id, "telegram")

    # Process pending messages (LLM will handle missing TZ)
    await _process_pending_queue_dm(callback.message.bot, user_id, chat_id, user_name)


@router.message(SetTimezone.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    """Process city name input."""
    data = await state.get_data()

    if data.get("user_id") != message.from_user.id:
        return

    is_dm = message.chat.type == "private"
    source_chat_id = data.get("source_chat_id")

    # In group chat (e.g. /tb_settz flow), clean up messages
    if not is_dm:
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

        if is_dm:
            prompt_msg = await message.answer(
                f"Could not find '{city_name}' (or service error).\n"
                "Enter your current time (e.g. 14:30) or try another city:"
            )
        else:
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

    is_dm = message.chat.type == "private"

    # In group chat, clean up messages
    if not is_dm:
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
    if is_dm:
        prompt_msg = await message.answer(
            f"Could not find '{user_input}'.\n"
            "Enter your current time (e.g. 14:30) or try another city:"
        )
    else:
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
    data = await state.get_data()
    username = message.from_user.username or ""
    user_name = message.from_user.first_name or "User"
    user_id = message.from_user.id
    is_dm = message.chat.type == "private"
    source_chat_id = data.get("source_chat_id")

    await storage.set_user(
        user_id=user_id,
        platform="telegram",
        city=location["city"],
        timezone=location["timezone"],
        flag=location["flag"],
        username=username
    )
    invalidate_user_cache(user_id, platform="telegram")

    # Add to chat members for the source group chat
    target_chat = source_chat_id if (is_dm and source_chat_id) else message.chat.id
    if target_chat != user_id:
        await storage.add_chat_member(target_chat, user_id, platform="telegram")

    await state.clear()

    # Confirm in the current chat (DM or group)
    await message.answer(f"✅ Set {user_name}: {location['city']} {location['flag']} ({location['timezone']})")

    # Clear the DM invite cooldown
    await clear_dm_invite(user_id, "telegram")

    # Process all pending messages — send results to the source group chat
    if is_dm and source_chat_id:
        await _process_pending_queue_dm(message.bot, user_id, source_chat_id, user_name)
    else:
        await _process_pending_queue(message, user_id, user_name)

    log_suffix = " (retry)" if is_retry else ""
    log_chat = source_chat_id if (is_dm and source_chat_id) else message.chat.id
    logger.info(f"[chat:{log_chat}] User {user_id} -> {location['timezone']}{log_suffix}")


async def _process_pending_queue(message: Message, user_id: int, user_name: str):
    """Helper to drain the pending queue for a user (group-chat context)."""
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


async def _process_pending_queue_dm(bot, user_id: int, chat_id: int, user_name: str):
    """Helper to drain the pending queue for a user (DM context — sends to source group chat)."""
    pending_list = await get_and_delete_pending_messages(user_id, "telegram")
    if not pending_list:
        return

    logger.info(f"[chat:{chat_id}] Draining {len(pending_list)} pending messages for user {user_id} (from DM)")

    user_record = await get_user_cached(user_id, platform="telegram")

    for pending in pending_list:
        async def send_reply_fn(text: str, _pending=pending) -> None:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_to_message_id=_pending.get("message_id")
            )

        snapshot = append_to_history("telegram", str(chat_id), pending)

        await process_message(
            message_text=pending["text"],
            chat_id=str(chat_id),
            user_id=str(user_id),
            platform="telegram",
            author_name=pending["author_name"],
            timestamp_utc=pending["timestamp_utc"],
            sender_db=user_record,
            send_fn=send_reply_fn,
            skip_history_append=True,
            precomputed_snapshot=snapshot
        )
