from datetime import datetime, timezone

import pytest

from adapters.outbound.memory_onboarding_chillout_state import MemoryOnboardingChilloutState
from adapters.outbound.memory_pending import MemoryOnboardingPending
from core.domain.enums import Platform
from core.domain.value_objects import InputData, OnboardingPendingMessage, TimePoint
from ports.detection import DetectionResult


def _pending_message(text: str, chat_id: str = "chat1") -> OnboardingPendingMessage:
    return OnboardingPendingMessage(
        original_input=InputData(
            text=text,
            user_id=1,
            platform=Platform.TELEGRAM,
            author_name="John",
            timestamp_utc=datetime.now(timezone.utc),
            chat_id=chat_id,
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

    await store.upsert(1, Platform.TELEGRAM, "chat1", _pending_message("first", chat_id="chat1"))
    await store.upsert(1, Platform.TELEGRAM, "chat1", _pending_message("second", chat_id="chat1"))

    message = await store.get(1, Platform.TELEGRAM, "chat1")

    assert message is not None
    assert message.original_input.text == "second"


@pytest.mark.asyncio
async def test_memory_onboarding_pending_keeps_latest_message_per_chat():
    now = [100.0]
    store = MemoryOnboardingPending(ttl_seconds=3600, now_fn=lambda: now[0])

    await store.upsert(1, Platform.TELEGRAM, "chat1", _pending_message("first", chat_id="chat1"))
    await store.upsert(1, Platform.TELEGRAM, "chat2", _pending_message("second", chat_id="chat2"))

    messages = await store.list_for_user(1, Platform.TELEGRAM)

    assert sorted(message.original_input.chat_id for message in messages) == ["chat1", "chat2"]


@pytest.mark.asyncio
async def test_memory_onboarding_pending_delete_clears_only_target_chat():
    now = [100.0]
    store = MemoryOnboardingPending(ttl_seconds=3600, now_fn=lambda: now[0])

    await store.upsert(1, Platform.TELEGRAM, "chat1", _pending_message("first", chat_id="chat1"))
    await store.upsert(1, Platform.TELEGRAM, "chat2", _pending_message("second", chat_id="chat2"))

    await store.delete(1, Platform.TELEGRAM, "chat1")

    assert await store.get(1, Platform.TELEGRAM, "chat1") is None
    assert await store.get(1, Platform.TELEGRAM, "chat2") is not None


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
