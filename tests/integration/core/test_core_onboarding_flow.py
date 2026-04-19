from datetime import datetime, timedelta, timezone

import pytest

from core.domain.commands import SendReply, ShowOnboarding
from core.domain.enums import Platform
from core.domain.value_objects import BotSettings, InputData, OnboardingPendingMessage, TimePoint, UserProfile
from core.pipeline.pipeline import Pipeline
from core.pipeline.stages import (
    AgingStage,
    DecisionStage,
    DetectionStage,
    FormatStage,
    GeoResolveStage,
    GuardStage,
    HydrationStage,
)
from adapters.outbound.delivery_service import DeliveryService
from core.services.message_processing import MessageProcessingService
from core.services.onboarding import OnboardingCoordinator
from ports.detection import DetectionResult
from tests.fakes.ports import (
    FakeCommandExecutorPort,
    FakeDetectionPort,
    FakeGeoPort,
    FakeOnboardingChilloutStatePort,
    FakeOnboardingPendingPort,
    FakeStoragePort,
)


def _make_fresh_pipeline(storage, detection, geo=None, settings=None):
    settings = settings or BotSettings()
    geo = geo or FakeGeoPort()
    return Pipeline([
        GuardStage(),
        AgingStage(settings),
        DetectionStage(detection),
        GeoResolveStage(geo),
        HydrationStage(storage),
        FormatStage(settings),
        DecisionStage(),
    ])


def _make_replay_pipeline(storage, settings=None):
    settings = settings or BotSettings()
    return Pipeline([
        HydrationStage(storage),
        FormatStage(settings),
        DecisionStage(),
    ])


def _make_services(
    *,
    storage=None,
    detection=None,
    pending=None,
    chillout=None,
    geo=None,
    settings=None,
):
    storage = storage or FakeStoragePort()
    detection = detection or FakeDetectionPort(time_mentioned=True, points=[TimePoint(time="12:00")])
    pending = pending or FakeOnboardingPendingPort()
    chillout = chillout or FakeOnboardingChilloutStatePort()
    geo = geo or FakeGeoPort()
    settings = settings or BotSettings()

    tg_executor = FakeCommandExecutorPort()
    delivery = DeliveryService(tg_executor=tg_executor)
    replay = _make_replay_pipeline(storage, settings)
    onboarding_coordinator = OnboardingCoordinator(
        storage_port=storage,
        onboarding_pending_port=pending,
        chillout_state_port=chillout,
        geocoding_port=geo,
        replay_pipeline=replay,
        delivery_service=delivery,
        settings=settings,
    )
    processor = MessageProcessingService(
        fresh_pipeline=_make_fresh_pipeline(storage, detection, geo, settings),
        storage_port=storage,
        delivery_service=delivery,
        onboarding_coordinator=onboarding_coordinator,
    )
    return storage, pending, chillout, onboarding_coordinator, processor, tg_executor


@pytest.mark.asyncio
async def test_message_processor_routes_reply_to_correct_executor():
    storage = FakeStoragePort()
    sender = UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/London", city="London", flag="🇬🇧")
    storage.users[(1, Platform.TELEGRAM)] = sender
    storage.members[("chat1", Platform.TELEGRAM)] = [sender]

    _, _, _, _, processor, tg_executor = _make_services(storage=storage)

    await processor.process_input(
        InputData(
            text="Let's meet at 12:00",
            user_id=1,
            platform=Platform.TELEGRAM,
            author_name="Alice",
            timestamp_utc=datetime.now(timezone.utc),
            chat_id="chat1",
        )
    )

    assert len(tg_executor.executed_commands) == 1
    assert isinstance(tg_executor.executed_commands[0], SendReply)


@pytest.mark.asyncio
async def test_fresh_message_without_timezone_saves_latest_pending_and_shows_prompt():
    pending = FakeOnboardingPendingPort()
    chillout = FakeOnboardingChilloutStatePort(in_chillout=False)
    storage, _, _, _, processor, tg_executor = _make_services(pending=pending, chillout=chillout)

    data = InputData(
        text="Let's meet at 12:00",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="Alice",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1",
    )
    await processor.process_input(data)

    assert (1, Platform.TELEGRAM, "Alice") in storage.created
    assert pending.messages[(1, Platform.TELEGRAM.value)].original_input.text == data.text
    assert len(tg_executor.executed_commands) == 1
    assert isinstance(tg_executor.executed_commands[0], ShowOnboarding)
    assert chillout.marked == [(1, Platform.TELEGRAM)]


@pytest.mark.asyncio
async def test_fresh_message_during_chillout_updates_pending_without_prompt():
    pending = FakeOnboardingPendingPort()
    chillout = FakeOnboardingChilloutStatePort(in_chillout=True)
    storage, _, _, _, processor, tg_executor = _make_services(pending=pending, chillout=chillout)

    data = InputData(
        text="Let's meet at 12:00",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="Alice",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1",
    )
    await processor.process_input(data)

    assert (1, Platform.TELEGRAM, "Alice") in storage.created
    assert pending.messages[(1, Platform.TELEGRAM.value)].original_input.text == data.text
    assert tg_executor.executed_commands == []
    assert chillout.marked == []


@pytest.mark.asyncio
async def test_complete_replays_latest_pending_and_clears_it():
    storage = FakeStoragePort()
    pending = FakeOnboardingPendingPort()
    geo = FakeGeoPort()
    geo._resolves_to = type("Location", (), {
        "city": "London",
        "timezone": "Europe/London",
        "country_code": "GB",
        "flag": "🇬🇧",
    })()
    _, pending, _, onboarding_coordinator, _, tg_executor = _make_services(storage=storage, pending=pending, geo=geo)

    receiver = UserProfile(user_id=2, platform=Platform.TELEGRAM, timezone="America/New_York", city="New York", flag="🇺🇸")
    storage.members[("chat1", Platform.TELEGRAM)] = [receiver]

    pending_msg = OnboardingPendingMessage(
        original_input=InputData(
            text="Let's meet at 12:00",
            user_id=1,
            platform=Platform.TELEGRAM,
            author_name="Alice",
            timestamp_utc=datetime.now(timezone.utc),
            chat_id="chat1",
        ),
        detection=DetectionResult(time_mentioned=True, points=(TimePoint(time="12:00"),)),
    )
    await pending.upsert(1, Platform.TELEGRAM, pending_msg)

    result = await onboarding_coordinator.complete(1, "London", Platform.TELEGRAM)

    assert result.ok is True
    assert len(tg_executor.executed_commands) == 1
    assert isinstance(tg_executor.executed_commands[0], SendReply)
    assert await pending.get(1, Platform.TELEGRAM) is None


@pytest.mark.asyncio
async def test_complete_drops_stale_pending_without_reply():
    storage = FakeStoragePort()
    pending = FakeOnboardingPendingPort()
    geo = FakeGeoPort()
    geo._resolves_to = type("Location", (), {
        "city": "London",
        "timezone": "Europe/London",
        "country_code": "GB",
        "flag": "🇬🇧",
    })()
    settings = BotSettings(max_age_fresh_secs=30)
    _, pending, _, onboarding_coordinator, _, tg_executor = _make_services(storage=storage, pending=pending, geo=geo, settings=settings)

    stale_msg = OnboardingPendingMessage(
        original_input=InputData(
            text="Let's meet at 12:00",
            user_id=1,
            platform=Platform.TELEGRAM,
            author_name="Alice",
            timestamp_utc=datetime.now(timezone.utc) - timedelta(minutes=10),
            chat_id="chat1",
        ),
        detection=DetectionResult(time_mentioned=True, points=(TimePoint(time="12:00"),)),
    )
    await pending.upsert(1, Platform.TELEGRAM, stale_msg)

    result = await onboarding_coordinator.complete(1, "London", Platform.TELEGRAM)

    assert result.ok is True
    assert tg_executor.executed_commands == []
    assert await pending.get(1, Platform.TELEGRAM) is None


@pytest.mark.asyncio
async def test_decline_marks_user_and_clears_pending():
    storage = FakeStoragePort()
    pending = FakeOnboardingPendingPort()
    _, pending, _, onboarding_coordinator, _, _ = _make_services(storage=storage, pending=pending)

    await pending.upsert(
        1,
        Platform.TELEGRAM,
        OnboardingPendingMessage(
            original_input=InputData(
                text="Let's meet at 12:00",
                user_id=1,
                platform=Platform.TELEGRAM,
                author_name="Alice",
                timestamp_utc=datetime.now(timezone.utc),
                chat_id="chat1",
            ),
            detection=DetectionResult(time_mentioned=True, points=(TimePoint(time="12:00"),)),
        ),
    )

    await onboarding_coordinator.decline(1, Platform.TELEGRAM)

    assert storage.users[(1, Platform.TELEGRAM)].onboarding_declined is True
    assert await pending.get(1, Platform.TELEGRAM) is None
