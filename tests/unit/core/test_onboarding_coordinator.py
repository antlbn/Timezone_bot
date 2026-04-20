from datetime import datetime, timedelta, timezone

import pytest

from core.domain.commands import SendReply
from core.domain.enums import Platform
from core.domain.value_objects import BotSettings, InputData, MessageContext, MessageDecision, OnboardingPendingMessage, TimePoint
from core.pipeline.pipeline import Pipeline
from adapters.outbound.delivery_service import DeliveryService
from core.services.onboarding import OnboardingCoordinator
from ports.detection import DetectionResult
from ports.geocoding import Location
from tests.fakes.ports import (
    FakeCommandExecutorPort,
    FakeGeoPort,
    FakeOnboardingChilloutStatePort,
    FakeOnboardingPendingPort,
    FakeStoragePort,
)


class StaticReplayStage:
    def __init__(self, decision: MessageDecision):
        self.decision = decision

    async def process(self, ctx: MessageContext) -> MessageContext:
        import dataclasses
        return dataclasses.replace(ctx, decision=self.decision)


def _pending_message(*, minutes_old: int = 0) -> OnboardingPendingMessage:
    return OnboardingPendingMessage(
        original_input=InputData(
            text="Meet at 15:00",
            user_id=1,
            platform=Platform.TELEGRAM,
            author_name="Alice",
            timestamp_utc=datetime.now(timezone.utc) - timedelta(minutes=minutes_old),
            chat_id="chat1",
            thread_id="thread-1",
        ),
        detection=DetectionResult(time_mentioned=True, points=(TimePoint(time="15:00"),)),
    )


def _coordinator(
    *,
    geo: FakeGeoPort | None = None,
    pending: FakeOnboardingPendingPort | None = None,
    chillout: FakeOnboardingChilloutStatePort | None = None,
    replay_decision: MessageDecision | None = None,
    settings: BotSettings | None = None,
):
    executor = FakeCommandExecutorPort()
    storage = FakeStoragePort()
    coordinator = OnboardingCoordinator(
        storage_port=storage,
        onboarding_pending_port=pending or FakeOnboardingPendingPort(),
        chillout_state_port=chillout or FakeOnboardingChilloutStatePort(),
        geocoding_port=geo or FakeGeoPort(),
        replay_pipeline=Pipeline([StaticReplayStage(replay_decision or MessageDecision(ignore=True))]),
        delivery_service=DeliveryService(tg_executor=executor),
        settings=settings or BotSettings(),
    )
    return coordinator, storage, executor


@pytest.mark.asyncio
async def test_store_pending_and_should_prompt_saves_latest_pending_and_checks_chillout():
    pending = FakeOnboardingPendingPort()
    chillout = FakeOnboardingChilloutStatePort(in_chillout=False)
    coordinator, _, _ = _coordinator(pending=pending, chillout=chillout)
    message = _pending_message()

    should_prompt = await coordinator.store_pending_and_should_prompt(1, Platform.TELEGRAM, message)

    assert should_prompt is True
    assert await pending.get(1, Platform.TELEGRAM) == message
    assert chillout.checked == [(1, Platform.TELEGRAM, 3600)]


@pytest.mark.asyncio
async def test_mark_prompt_shown_delegates_to_chillout_state():
    chillout = FakeOnboardingChilloutStatePort()
    coordinator, _, _ = _coordinator(chillout=chillout)

    await coordinator.mark_prompt_shown(1, Platform.TELEGRAM)

    assert chillout.marked == [(1, Platform.TELEGRAM)]


@pytest.mark.asyncio
async def test_complete_returns_city_not_found_without_side_effects():
    coordinator, storage, executor = _coordinator(geo=FakeGeoPort(resolves_to=None))

    result = await coordinator.complete(1, "Unknown", Platform.TELEGRAM)

    assert result.ok is False
    assert result.error == "city_not_found"
    assert storage.users == {}
    assert executor.executed_commands == []


@pytest.mark.asyncio
async def test_complete_replays_pending_reply_and_clears_pending():
    pending = FakeOnboardingPendingPort()
    message = _pending_message()
    await pending.upsert(1, Platform.TELEGRAM, message)
    geo = FakeGeoPort(
        resolves_to=Location(city="London", timezone="Europe/London", country_code="GB", flag="🇬🇧")
    )
    coordinator, storage, executor = _coordinator(
        geo=geo,
        pending=pending,
        replay_decision=MessageDecision(reply_text="15:00 London"),
    )

    result = await coordinator.complete(1, "London", Platform.TELEGRAM)

    assert result.ok is True
    assert storage.users[(1, Platform.TELEGRAM)].timezone == "Europe/London"
    assert executor.executed_commands == [
        SendReply(text="15:00 London", chat_id="chat1", thread_id="thread-1")
    ]
    assert await pending.get(1, Platform.TELEGRAM) is None


@pytest.mark.asyncio
async def test_complete_drops_stale_pending_without_delivery():
    pending = FakeOnboardingPendingPort()
    await pending.upsert(1, Platform.TELEGRAM, _pending_message(minutes_old=10))
    geo = FakeGeoPort(
        resolves_to=Location(city="London", timezone="Europe/London", country_code="GB", flag="🇬🇧")
    )
    coordinator, _, executor = _coordinator(
        geo=geo,
        pending=pending,
        settings=BotSettings(max_age_fresh_secs=30),
    )

    result = await coordinator.complete(1, "London", Platform.TELEGRAM)

    assert result.ok is True
    assert executor.executed_commands == []
    assert await pending.get(1, Platform.TELEGRAM) is None


@pytest.mark.asyncio
async def test_decline_marks_storage_and_clears_pending():
    """decline() → set_onboarding_declined called, pending deleted."""
    pending = FakeOnboardingPendingPort()
    await pending.upsert(1, Platform.TELEGRAM, _pending_message())
    coordinator, storage, _ = _coordinator(pending=pending)

    await coordinator.decline(1, Platform.TELEGRAM)

    assert storage.users[(1, Platform.TELEGRAM)].onboarding_declined is True
    assert await pending.get(1, Platform.TELEGRAM) is None
