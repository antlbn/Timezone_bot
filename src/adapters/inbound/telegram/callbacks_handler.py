from aiogram import Router, F
from aiogram.types import CallbackQuery, ForceReply
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
import logging

from core.domain.enums import Platform
from adapters.inbound.telegram.onboarding_handler import OnboardingFSM
from adapters.inbound.telegram import ui
from adapters.inbound.telegram.ui import TelegramCallback, get_settings_keyboard, get_help_text, get_back_to_settings_keyboard
from adapters.inbound.telegram.common import safe_edit_text, safe_delete_message, PRIVATE_CHAT_SENTINEL
from core.services.profile import ProfileService
from core.services.onboarding import OnboardingCompletionUseCase

router = Router(name="callbacks")
logger = logging.getLogger(__name__)

@router.callback_query(TelegramCallback.filter(F.action == "set_city"), StateFilter("*"))
async def cb_set_city(callback: CallbackQuery, callback_data: TelegramCallback, state: FSMContext):
    if callback.from_user.id != callback_data.user_id:
        await callback.answer(ui.get_not_your_button_text(), show_alert=True)
        return

    await state.set_state(OnboardingFSM.waiting_city)
    if callback_data.chat_id and callback_data.chat_id != PRIVATE_CHAT_SENTINEL:
        await state.update_data(source_chat_id=callback_data.chat_id)

    await callback.message.answer(
        ui.get_city_prompt_text(),
        reply_markup=ForceReply(selective=True)
    )
    await safe_delete_message(callback.message)
    await callback.answer()

@router.callback_query(TelegramCallback.filter(F.action == "decline"), StateFilter("*"))
async def cb_decline(
    callback: CallbackQuery, 
    callback_data: TelegramCallback, 
    state: FSMContext,
    onboarding_completion: OnboardingCompletionUseCase
):
    if callback.from_user.id != callback_data.user_id:
        await callback.answer(ui.get_not_your_button_text(), show_alert=True)
        return

    await state.clear()
    await onboarding_completion.decline(
        user_id=callback_data.user_id,
        platform=Platform.TELEGRAM
    )
    
    await safe_edit_text(
        callback,
        ui.get_decline_confirmation_text(),
        reply_markup=get_settings_keyboard(callback_data.user_id, callback_data.chat_id, has_timezone=False)
    )
    await callback.answer("Bot services declined.")

@router.callback_query(TelegramCallback.filter(F.action == "remove"), StateFilter("*"))
async def cb_remove(
    callback: CallbackQuery, 
    callback_data: TelegramCallback, 
    profile_service: ProfileService
):
    if callback.from_user.id != callback_data.user_id:
        await callback.answer(ui.get_not_your_button_text(), show_alert=True)
        return

    await profile_service.remove_timezone(
        user_id=callback_data.user_id,
        platform=Platform.TELEGRAM,
        username=callback.from_user.first_name
    )
    
    await safe_edit_text(
        callback,
        ui.get_timezone_removed_text(),
        reply_markup=get_settings_keyboard(callback_data.user_id, callback_data.chat_id, has_timezone=False)
    )
    await callback.answer("Timezone removed.")

@router.callback_query(TelegramCallback.filter(F.action == "privacy"), StateFilter("*"))
async def cb_privacy(callback: CallbackQuery):
    await callback.answer(
        ui.get_privacy_text(),
        show_alert=True
    )

@router.callback_query(TelegramCallback.filter(F.action == "help"), StateFilter("*"))
async def cb_help(callback: CallbackQuery, callback_data: TelegramCallback):
    if callback.from_user.id != callback_data.user_id:
        await callback.answer(ui.get_not_your_button_text(), show_alert=True)
        return

    await safe_edit_text(
        callback,
        get_help_text(),
        reply_markup=get_back_to_settings_keyboard(callback_data.user_id, callback_data.chat_id)
    )
    await callback.answer()

@router.callback_query(TelegramCallback.filter(F.action == "settings"), StateFilter("*"))
async def cb_settings(
    callback: CallbackQuery, 
    callback_data: TelegramCallback, 
    profile_service: ProfileService
):
    if callback.from_user.id != callback_data.user_id:
        await callback.answer(ui.get_not_your_button_text(), show_alert=True)
        return

    user = await profile_service.get_user(callback_data.user_id, Platform.TELEGRAM)
    is_timezone_set = user is not None and user.timezone is not None
    
    await safe_edit_text(
        callback,
        ui.get_main_settings_text(),
        reply_markup=get_settings_keyboard(callback_data.user_id, callback_data.chat_id, has_timezone=is_timezone_set)
    )
    await callback.answer()

@router.callback_query()
async def cb_fallback(callback: CallbackQuery):
    """Log unhandled callbacks to help debug legacy interaction issues."""
    logger.warning(f"Unhandled callback data: {callback.data} from user {callback.from_user.id}")
    await callback.answer(
        ui.get_legacy_callback_text(),
        show_alert=True
    )
