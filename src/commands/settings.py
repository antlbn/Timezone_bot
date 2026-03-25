from aiogram import Router, F
from aiogram.types import (
    Message,
    ForceReply,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext

from src.storage import storage
from src.storage.user_cache import get_user_cached, invalidate_user_cache
from src.storage.pending import (
    clear_dm_invite,
)
from src import geo
from src.logger import get_logger
from src.commands.states import SetTimezone
from src.commands.utils import auto_cleanup

router = Router()
logger = get_logger()

# ---------------------------------------------------------------------------
# DM Onboarding — Deep Link flow
# ---------------------------------------------------------------------------


@router.message(CommandStart(), F.chat.type == "private")
@auto_cleanup(delete_bot_msg=True, keep_bot_msg_in_dm=True)
async def dm_onboarding_start(
    message: Message, command: CommandObject, state: FSMContext
):
    """
    Handle /start in DM.
    If payload is 'onboard_{user_id}_{chat_id}', it's a deep link from a group chat.
    Otherwise, it's a direct user interaction.
    """
    user_id = message.from_user.id
    payload = command.args
    chat_id = 0  # Default to 0 (no source chat)

    if payload and payload.startswith("onboard_"):
        try:
            parts = payload.split("_")
            target_user_id = int(parts[1])
            chat_id = int(parts[2])

            # Security: only the target user can trigger their own onboarding deep link
            if user_id != target_user_id:
                await message.answer("This link is not for you! 😊")
                return
        except (IndexError, ValueError):
            logger.warning(f"Invalid onboarding deep link payload: {payload}")

    user_name = message.from_user.first_name or "User"

    # If user already has a timezone, show the Settings Menu immediately
    existing = await get_user_cached(user_id, platform="telegram")
    if existing and existing.get("timezone"):
        return await show_dm_settings_menu(message, existing, user_id, chat_id)

    welcome_text = (
        f"👋 Hi {user_name}!\n"
        f"\n"
        f"🤖 *What I am*\n"
        f"I'm a bot that converts times for chat members across "
        f"different cities and time zones. When someone mentions a time, "
        f"I show what it is for everyone else.\n"
        f"\n"
        f"💬 *How to use me*\n"
        f"You don't need to do anything special — just chat as usual. "
        f"I'll detect when someone talks about events and times, and "
        f"reply with the converted time automatically.\n"
        f"\n"
        f"⚙️ *Set up your location*\n"
        f"To get started, I need to know your city. You can always change this "
        f"later or remove your data by coming back here or using `/tb_help` in any chat.\n"
        f"\n"
        f"Ready? Tap *Set my city* below 👇"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📍 Set my city",
                    callback_data=f"dm_setcity:{user_id}:{chat_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✖️ No thanks", callback_data=f"dm_decline:{user_id}:{chat_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔒 Data Privacy", callback_data=f"dm_privacy:{user_id}"
                )
            ],
        ]
    )

    # Store chat_id (0 if none) to state
    await state.update_data(user_id=user_id, source_chat_id=chat_id)
    return await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("dm_setcity:"))
async def dm_setcity_callback(callback: CallbackQuery, state: FSMContext):
    """Handle 'Set my city' button click in DM — transition to city input."""
    parts = callback.data.split(":")
    try:
        user_id = int(parts[1])
        chat_id = int(parts[2])
    except (IndexError, ValueError):
        await callback.answer("Error processing request.")
        return

    if callback.from_user.id != user_id:
        await callback.answer("This button is not for you! 😊", show_alert=True)
        return

    user_name = callback.from_user.first_name or "User"

    # Remove buttons from the welcome message
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logger.warning(f"Failed to remove welcome buttons: {e}")

    await callback.message.answer(
        f"Great {user_name}! Tell me your city so I can show your local time to others.\n"
        f"\n"
        f"💡 For best results, write it as: `City, Country` \n"
        f"e.g. `Paris, France` or `Paris, Texas, USA`.",
        parse_mode="Markdown",
    )
    await state.set_state(SetTimezone.waiting_for_city)
    await state.update_data(user_id=user_id, source_chat_id=chat_id)
    await callback.answer()


@router.callback_query(F.data.startswith("dm_privacy:"))
async def dm_privacy_callback(callback: CallbackQuery):
    """Show data privacy information."""
    from src.config import get_data_retention_days

    retention_days = get_data_retention_days()

    await callback.answer(
        text=f"Data is stored locally and auto-deleted after {retention_days} days of inactivity.",
        show_alert=True,
    )
    # Alternatively, send as a message if alert is too small
    # but the user said "сделаем кнопкой (там просто будет текст о том как дата храниться)"
    # A pop-up alert is usually best for this.


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
        onboarding_declined=True,
    )
    invalidate_user_cache(user_id, platform="telegram")

    # Clear FSM state
    await state.clear()

    # Acknowledge in DM and show menu with "Set again" option implicitly
    await callback.message.edit_text(
        "Got it! I won't nag you again. If you change your mind, use the menu below or /tb_settz in any chat.",
        reply_markup=await get_dm_settings_markup(user_id, chat_id, is_declined=True),
    )
    await callback.answer()

    # Clear the DM invite cooldown
    await clear_dm_invite(user_id, "telegram")

# ---------------------------------------------------------------------------
# Settings Menu — Registered Users
# ---------------------------------------------------------------------------


async def get_dm_settings_markup(
    user_id: int, chat_id: int, is_declined: bool = False
) -> InlineKeyboardMarkup:
    """Helper to build the Settings Menu keyboard."""
    buttons = []

    if is_declined:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="📍 Set timezone",
                    callback_data=f"dm_change_city:{user_id}:{chat_id}",
                )
            ]
        )
    else:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🔄 Change timezone",
                    callback_data=f"dm_change_city:{user_id}:{chat_id}",
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🗑️ Remove timezone",
                    callback_data=f"dm_remove_city:{user_id}:{chat_id}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="ℹ️ More settings",
                callback_data=f"dm_extra_settings:{user_id}:{chat_id}",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_dm_settings_menu(
    message: Message, user_record: dict, user_id: int, chat_id: int
):
    """Show the Settings Menu in DM."""
    city = user_record.get("city")
    timezone = user_record.get("timezone")
    flag = user_record.get("flag", "")

    text = (
        f"✅ Your timezone is set to: *{city} {flag}* ({timezone})\n"
        "\nYou can manage your settings here:"
    )

    return await message.answer(
        text,
        reply_markup=await get_dm_settings_markup(user_id, chat_id),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("dm_change_city:"))
async def dm_change_city_callback(callback: CallbackQuery, state: FSMContext):
    """Callback to trigger city input from the Settings Menu."""
    parts = callback.data.split(":")
    user_id, chat_id = int(parts[1]), int(parts[2])

    if callback.from_user.id != user_id:
        await callback.answer("This button is not for you! 😊", show_alert=True)
        return

    await state.set_state(SetTimezone.waiting_for_city)
    await state.update_data(user_id=user_id, source_chat_id=chat_id)

    await callback.message.edit_text(
        "Sure! What city are you in now?\n💡 Tip: `City, Country` works best.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dm_remove_city:"))
async def dm_remove_city_callback(callback: CallbackQuery, state: FSMContext):
    """Callback to remove timezone from the Settings Menu."""
    parts = callback.data.split(":")
    user_id, chat_id = int(parts[1]), int(parts[2])

    if callback.from_user.id != user_id:
        await callback.answer("This button is not for you! 😊", show_alert=True)
        return

    # Clear city/timezone in DB
    await storage.set_user(
        user_id=user_id,
        platform="telegram",
        city=None,
        timezone=None,
        username=callback.from_user.username or "",
        onboarding_declined=False,  # Reset declined so they can be re-onboarded later if needed
    )
    invalidate_user_cache(user_id, platform="telegram")

    await callback.message.edit_text(
        "🗑️ Your timezone has been removed. I'll no longer convert times for you.\n"
        "If you want to set it again later, tap below.",
        reply_markup=await get_dm_settings_markup(user_id, chat_id, is_declined=True),
    )
    await callback.answer("Timezone removed.")


@router.callback_query(F.data.startswith("dm_extra_settings:"))
async def dm_extra_settings_callback(callback: CallbackQuery):
    """Show additional settings / commands info."""
    parts = callback.data.split(":")
    user_id, chat_id = int(parts[1]), int(parts[2])

    text = (
        "⚙️ *Additional Settings & Commands*\n"
        "\n"
        "These commands work in **group chats** where I am present:\n"
        "\n"
        "👥 `/tb_members` — Lists all members I am currently tracking in that chat.\n"
        "\n"
        "🗑 `/tb_remove` — Manually remove a member from the list. Use this if someone left the group.\n"
        "\n"
        "📋 *Chat members*: I only track members who send messages. "
        "I don't have access to the full member list. "
        "Use the commands above to manage tracked members.\n"
        "\n"
        "💡 *Note:* I automatically remove inactive users after 30 days of silence."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Back to menu",
                    callback_data=f"dm_back_menu:{user_id}:{chat_id}",
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("dm_back_menu:"))
async def dm_back_menu_callback(callback: CallbackQuery):
    """Callback to return to the main settings menu."""
    parts = callback.data.split(":")
    user_id, chat_id = int(parts[1]), int(parts[2])

    user_record = await get_user_cached(user_id, platform="telegram")
    if not user_record or not user_record.get("timezone"):
        # If they somehow removed it and went back
        await callback.message.edit_text(
            "You haven't set your timezone yet.",
            reply_markup=await get_dm_settings_markup(
                user_id, chat_id, is_declined=True
            ),
        )
    else:
        city = user_record.get("city")
        timezone = user_record.get("timezone")
        flag = user_record.get("flag", "")

        text = (
            f"✅ Your timezone is set to: *{city} {flag}* ({timezone})\n"
            "\nYou can manage your settings here:"
        )
        await callback.message.edit_text(
            text,
            reply_markup=await get_dm_settings_markup(user_id, chat_id),
            parse_mode="Markdown",
        )
    await callback.answer()


@router.message(SetTimezone.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    """Process city name input."""
    data = await state.get_data()

    if data.get("user_id") != message.from_user.id:
        return

    is_dm = message.chat.type == "private"

    # In group chat (e.g. /tb_settz flow), clean up messages
    if not is_dm:
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete user's message: {e}")

        try:
            if data.get("prompt_message_id"):
                await message.bot.delete_message(
                    chat_id=message.chat.id, message_id=data["prompt_message_id"]
                )
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
                reply_markup=ForceReply(selective=True),
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
                await message.bot.delete_message(
                    chat_id=message.chat.id, message_id=data["prompt_message_id"]
                )
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
            reply_markup=ForceReply(selective=True),
        )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    # Stay in waiting_for_time state for retry


async def _save_and_finish(
    message: Message, state: FSMContext, location: dict, is_retry: bool = False
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
        username=username,
    )
    invalidate_user_cache(user_id, platform="telegram")

    # Add to chat members for the source group chat
    target_chat = source_chat_id if (is_dm and source_chat_id) else message.chat.id
    if target_chat != user_id:
        await storage.add_chat_member(target_chat, user_id, platform="telegram")

    await state.clear()

    # Confirm and show management menu in DM
    if is_dm:
        # If we have a prompt message (Welcome message), we can edit it or just send a new one
        # To avoid confusion, let's send a new "Success" message that acts as the menu
        await show_dm_settings_menu(message, location, user_id, source_chat_id)
    else:
        # Group chat confirm (standard /tb_settz flow)
        await message.answer(
            f"✅ Set {user_name}: {location['city']} {location['flag']} ({location['timezone']})"
        )

    # Clear the DM invite cooldown
    await clear_dm_invite(user_id, "telegram")

    log_suffix = " (retry)" if is_retry else ""
    log_chat = source_chat_id if (is_dm and source_chat_id) else message.chat.id
    logger.info(
        f"[chat:{log_chat}] User {user_id} -> {location['timezone']}{log_suffix}"
    )
