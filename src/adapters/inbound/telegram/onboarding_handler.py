"""
Telegram-specific onboarding FSM handler.

Responsibilities (adapter layer only):
  - Parse Telegram events (Message objects)
  - Manage aiogram FSM state transitions
  - Call OnboardingCompletionUseCase (application layer)
  - Execute returned dispatches via bot.send_message

This handler knows nothing about geocoding, storage, or the pipeline.
author_name is passed to OnboardingCompletionUseCase to ensure user metadata 
is up to date during the completion stage.
"""

from typing import TYPE_CHECKING
import logging

from aiogram import Router, F
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ForceReply

from core.domain.enums import Platform
from adapters.inbound.telegram import ui
from adapters.inbound.telegram.ui import get_settings_keyboard
from adapters.inbound.telegram.config import TelegramConfig
from adapters.inbound.telegram.common import parse_onboarding_payload, PRIVATE_CHAT_SENTINEL, DeletionScheduler
from core.services.onboarding import OnboardingCompletionUseCase
from core.services.profile import ProfileService

if TYPE_CHECKING:
    pass

router = Router(name="onboarding")
logger = logging.getLogger(__name__)

class OnboardingFSM(StatesGroup):
    waiting_city = State()


@router.message(CommandStart())
async def on_start_command(
    message: Message, 
    command: CommandObject, 
    state: FSMContext, 
    onboarding_completion: OnboardingCompletionUseCase,
    profile_service: ProfileService,
    tg_config: TelegramConfig,
    deletion_scheduler: DeletionScheduler,
) -> None:
    """Entry point for private onboarding, including validated deep links."""
    await start_onboarding_flow(message, state, onboarding_completion, profile_service, tg_config, deletion_scheduler, command)


async def start_onboarding_flow(
    message: Message, 
    state: FSMContext, 
    onboarding_completion: OnboardingCompletionUseCase,
    profile_service: ProfileService,
    tg_config: TelegramConfig,
    deletion_scheduler: DeletionScheduler,
    command: CommandObject | None = None
) -> None:
    """Shared logic for starting onboarding from command or group redirect."""
    start_context = parse_onboarding_payload(command.args if command else None)
    if start_context is not None and message.from_user.id != start_context.target_user_id:
        await message.answer(ui.get_wrong_user_link_text())
        return

    chat_id = PRIVATE_CHAT_SENTINEL
    if start_context is not None and start_context.source_chat_id:
        chat_id = start_context.source_chat_id
        await state.update_data(source_chat_id=chat_id)

    # Check if user already exists
    user = await profile_service.get_user(message.from_user.id, Platform.TELEGRAM)
    
    if user and user.timezone:
        reply = await message.answer(
            ui.get_already_set_text(user.city, user.flag, user.timezone),
            reply_markup=get_settings_keyboard(message.from_user.id, chat_id, has_timezone=True)
        )
    else:
        reply = await message.answer(
            ui.get_onboarding_greeting_text(message.from_user.first_name or 'there'),
            reply_markup=get_settings_keyboard(message.from_user.id, chat_id, has_timezone=False)
        )
    
    await deletion_scheduler.schedule(reply, delay=tg_config.delete_delay)

@router.message(OnboardingFSM.waiting_city, F.text)
async def on_city_input(
    message: Message, 
    state: FSMContext, 
    onboarding_completion: OnboardingCompletionUseCase
) -> None:
    """User typed a city name."""
    city_raw = message.text.strip()
    
    # Check for cancellation intent
    if city_raw.lower() in ("cancel", "stop", "отмена", "стоп", "exit"):
        await state.clear()
        await message.answer("Setup cancelled. You can start again with /tb_settz anytime!")
        return

    user_id = message.from_user.id
    state_data = await state.get_data()


    result = await onboarding_completion.complete(
        user_id=user_id,
        city_raw=city_raw,
        platform=Platform.TELEGRAM,
        author_name=message.from_user.first_name,
    )

    if not result.ok:
        await message.answer(
            ui.get_city_not_found_text(city_raw),
            reply_markup=ForceReply(selective=True)
        )
        return

    await state.clear()
    await message.answer(
        ui.get_completion_text(result.timezone_name, result.flag),
        reply_markup=get_settings_keyboard(user_id, state_data.get("source_chat_id", PRIVATE_CHAT_SENTINEL), has_timezone=True)
    )
