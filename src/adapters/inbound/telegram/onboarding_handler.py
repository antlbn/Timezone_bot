"""
Telegram-specific onboarding FSM handler.

Responsibilities (adapter layer only):
  - Parse Telegram events (Message objects)
  - Manage aiogram FSM state transitions
  - Call OnboardingService (application layer)
  - Execute returned dispatches via bot.send_message

This handler knows nothing about geocoding, storage, or the pipeline.
"""

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from src.core.domain.enums import Platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.main import AppContainer

router = Router(name="onboarding")


# ---------------------------------------------------------------------------
# FSM States
# ---------------------------------------------------------------------------

class OnboardingFSM(StatesGroup):
    waiting_city = State()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@router.message(CommandStart(deep_link=True, magic=F.args == "onboard"))
async def on_start_onboard(message: Message, state: FSMContext) -> None:
    """Entry point: user tapped the deep-link button from a group chat."""
    await state.set_state(OnboardingFSM.waiting_city)
    await message.answer(
        "🌍 <b>Напиши свой город</b> — я определю часовой пояс.\n"
        "Или /skip, чтобы пропустить."
    )


@router.message(OnboardingFSM.waiting_city, F.text.startswith("/skip"))
async def on_skip(message: Message, state: FSMContext, container: "AppContainer") -> None:
    """User chose not to provide location."""
    await state.clear()
    await container.onboarding_service.decline(
        user_id=message.from_user.id,
        platform=Platform.TELEGRAM,
        author_name=message.from_user.full_name,
    )
    await message.answer("Окей, не буду спрашивать 🙂 Если передумаешь — /start")


@router.message(OnboardingFSM.waiting_city, F.text)
async def on_city_input(message: Message, state: FSMContext, container: "AppContainer") -> None:
    """User typed a city name."""
    city_raw = message.text.strip()
    user_id = message.from_user.id

    # ── call application service ──────────────────────────────────────────
    result = await container.onboarding_service.complete(
        user_id=user_id,
        city_raw=city_raw,
        platform=Platform.TELEGRAM,
        author_name=message.from_user.full_name,
    )

    if not result.ok:
        await message.answer(
            f"Не нашёл город «{city_raw}» 🤔\n"
            "Попробуй написать по-английски или /skip."
        )
        # stay in waiting_city state so user can retry
        return

    await state.clear()
    await message.answer(
        f"✅ Установлено: <b>{result.timezone_name}</b> {result.flag or ''}"
    )
