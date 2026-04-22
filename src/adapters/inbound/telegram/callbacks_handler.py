from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
import logging

from core.domain.enums import Platform
from adapters.inbound.telegram.onboarding_handler import OnboardingFSM
from adapters.inbound.telegram.ui import TelegramCallback, get_settings_keyboard
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import AppContainer

router = Router(name="callbacks")
logger = logging.getLogger(__name__)

@router.callback_query(TelegramCallback.filter(F.action == "set_city"), StateFilter("*"))
async def cb_set_city(callback: CallbackQuery, callback_data: TelegramCallback, state: FSMContext):
    if callback.from_user.id != callback_data.user_id:
        await callback.answer("This button is not for you! 😊", show_alert=True)
        return

    await state.set_state(OnboardingFSM.waiting_city)
    if callback_data.chat_id and callback_data.chat_id != "0":
        await state.update_data(source_chat_id=callback_data.chat_id)

    await callback.message.answer(
        "Great! Tell me your city so I can show your local time to others.\n"
        "💡 Write city: e.g. <code>Paris</code> or <code>Paris, Texas</code>.",
        reply_markup=ForceReply(selective=True)
    )
    await callback.message.delete()
    await callback.answer()

@router.callback_query(TelegramCallback.filter(F.action == "decline"), StateFilter("*"))
async def cb_decline(callback: CallbackQuery, callback_data: TelegramCallback, container: "AppContainer"):
    if callback.from_user.id != callback_data.user_id:
        await callback.answer("This button is not for you! 😊", show_alert=True)
        return

    await container.onboarding_completion.decline(
        user_id=callback_data.user_id,
        platform=Platform.TELEGRAM
    )
    
    await callback.message.edit_text(
        "Got it! I won't nag you again. If you change your mind, use /tb_settz.",
        reply_markup=get_settings_keyboard(callback_data.user_id, callback_data.chat_id, has_timezone=False)
    )
    await callback.answer("Onboarding declined.")

@router.callback_query(TelegramCallback.filter(F.action == "remove"), StateFilter("*"))
async def cb_remove(callback: CallbackQuery, callback_data: TelegramCallback, container: "AppContainer"):
    if callback.from_user.id != callback_data.user_id:
        await callback.answer("This button is not for you! 😊", show_alert=True)
        return

    await container.profile_service.remove_timezone(
        user_id=callback_data.user_id,
        platform=Platform.TELEGRAM,
        username=callback.from_user.first_name
    )
    
    await callback.message.edit_text(
        "🗑️ Your timezone has been removed. I'll no longer convert times for you.",
        reply_markup=get_settings_keyboard(callback_data.user_id, callback_data.chat_id, has_timezone=False)
    )
    await callback.answer("Timezone removed.")

@router.callback_query(TelegramCallback.filter(F.action == "privacy"), StateFilter("*"))
async def cb_privacy(callback: CallbackQuery):
    await callback.answer(
        "Data is stored locally and used only for time conversion. "
        "User profiles are automatically deleted after 30 days of inactivity.",
        show_alert=True
    )

@router.callback_query()
async def cb_fallback(callback: CallbackQuery):
    """Log unhandled callbacks to help debug legacy interaction issues."""
    logger.warning(f"Unhandled callback data: {callback.data} from user {callback.from_user.id}")
    await callback.answer(
        "This button belongs to an older version of the bot and is no longer active. "
        "Please use /tb_settz to get a new menu.",
        show_alert=True
    )
