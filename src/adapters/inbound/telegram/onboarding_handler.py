"""
Telegram-specific onboarding FSM handler.

Responsibilities (adapter layer only):
  - Parse Telegram events (Message objects)
  - Manage aiogram FSM state transitions
  - Call OnboardingCompletionUseCase (application layer)
  - Execute returned dispatches via bot.send_message

This handler knows nothing about geocoding, storage, or the pipeline.
author_name is NOT passed to OnboardingCompletionUseCase — it was already
synced to the DB when the original time message was processed.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING
import logging

from aiogram import Router, F, Bot
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ForceReply

from core.domain.enums import Platform
from adapters.inbound.telegram.ui import get_settings_keyboard

if TYPE_CHECKING:
    from main import AppContainer

router = Router(name="onboarding")
logger = logging.getLogger(__name__)

from adapters.inbound.telegram.common import parse_onboarding_payload, OnboardingStartContext

class OnboardingFSM(StatesGroup):
    waiting_city = State()

@router.message(CommandStart(), F.chat.type == "private", StateFilter("*"))
async def on_start_onboard(
    message: Message,
    state: FSMContext,
    container: "AppContainer",
    command: CommandObject | None = None,
) -> None:
    """Entry point for private onboarding, including validated deep links."""
    start_context = parse_onboarding_payload(command.args if command else None)
    if start_context is not None and message.from_user.id != start_context.target_user_id:
        await message.answer("This setup link belongs to another user.")
        return

    chat_id = "0"
    if start_context is not None and start_context.source_chat_id:
        chat_id = start_context.source_chat_id
        await state.update_data(source_chat_id=chat_id)

    # Check if user already exists
    user = await container.profile_service.get_user(message.from_user.id, Platform.TELEGRAM)
    
    if user and user.timezone:
        await message.answer(
            f"✅ Your timezone is set to: <b>{user.city} {user.flag or ''}</b> ({user.timezone})\n"
            "\nYou can manage your settings here:",
            reply_markup=get_settings_keyboard(message.from_user.id, chat_id, has_timezone=True)
        )
    else:
        text = (
            f"👋 Hi {message.from_user.first_name or 'there'}!\n\n"
            "I'm a bot that converts times for chat members across different cities and time zones. "
            "To show your local time to others, I need to know your city.\n\n"
            "Ready? Tap <b>Set my city</b> below 👇"
        )
        await message.answer(
            text,
            reply_markup=get_settings_keyboard(message.from_user.id, chat_id, has_timezone=False)
        )

@router.message(OnboardingFSM.waiting_city, F.text)
async def on_city_input(message: Message, state: FSMContext, container: "AppContainer") -> None:
    """User typed a city name."""
    city_raw = message.text.strip()
    user_id = message.from_user.id
    state_data = await state.get_data()

    result = await container.onboarding_completion.complete(
        user_id=user_id,
        city_raw=city_raw,
        platform=Platform.TELEGRAM,
        author_name=message.from_user.first_name,
    )

    if not result.ok:
        await message.answer(
            f"Could not find city «{city_raw}» 🤔\n"
            "Try writing in English or use /tb_decline to skip.",
            reply_markup=ForceReply(selective=True)
        )
        return

    await state.clear()
    await message.answer(
        f"✅ Set to: <b>{result.timezone_name}</b> {result.flag or ''}\n\n"
        "From now on, I will automatically convert time for you!",
        reply_markup=get_settings_keyboard(user_id, state_data.get("source_chat_id", "0"), has_timezone=True)
    )
