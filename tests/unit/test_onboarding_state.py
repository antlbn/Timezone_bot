from datetime import datetime, timezone

import pytest

from adapters.outbound.memory_onboarding_chillout_state import MemoryOnboardingChilloutState
from adapters.outbound.memory_pending import MemoryOnboardingPending
from core.domain.enums import Platform
from core.domain.value_objects import InputData, OnboardingPendingMessage, TimePoint
from ports.detection import DetectionResult


def _pending_message(text: str) -> OnboardingPendingMessage:
    return OnboardingPendingMessage(
        original_input=InputData(
            text=text,
            user_id=1,
            platform=Platform.TELEGRAM,
            author_name="John",
            timestamp_utc=datetime.now(timezone.utc),
            chat_id="chat1",
        ),
        detection=DetectionResult(
            time_mentioned=True,
            points=(TimePoint(time="15:00"),),
        ),
    )


@pytest.mark.asyncio
async def test_memory_onboarding_pending_upsert_replaces_previous_message():
    now = [100.0]
    store = MemoryOnboardingPending(ttl_seconds=3600, now_fn=lambda: now[0])

    await store.upsert(1, Platform.TELEGRAM, _pending_message("first"))
    await store.upsert(1, Platform.TELEGRAM, _pending_message("second"))

    message = await store.get_and_delete(1, Platform.TELEGRAM)

    assert message is not None
    assert message.original_input.text == "second"


@pytest.mark.asyncio
async def test_memory_onboarding_pending_get_and_delete_clears_value():
    now = [100.0]
    store = MemoryOnboardingPending(ttl_seconds=3600, now_fn=lambda: now[0])

    await store.upsert(1, Platform.TELEGRAM, _pending_message("latest"))

    first = await store.get_and_delete(1, Platform.TELEGRAM)
    second = await store.get_and_delete(1, Platform.TELEGRAM)

    assert first is not None
    assert second is None


@pytest.mark.asyncio
async def test_memory_onboarding_chillout_state_is_active_after_mark():
    now = [100.0]
    state = MemoryOnboardingChilloutState(now_fn=lambda: now[0])

    await state.mark_onboarding_shown(1, Platform.TELEGRAM)

    assert await state.is_onboarding_in_chillout(1, Platform.TELEGRAM, 600) is True


@pytest.mark.asyncio
async def test_memory_onboarding_chillout_state_expires_after_timeout():
    now = [100.0]
    state = MemoryOnboardingChilloutState(now_fn=lambda: now[0])

    await state.mark_onboarding_shown(1, Platform.TELEGRAM)
    now[0] = 1000.0

    assert await state.is_onboarding_in_chillout(1, Platform.TELEGRAM, 600) is False
