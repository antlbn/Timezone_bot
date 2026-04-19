import pytest
from datetime import datetime, timezone

from core.domain.enums import Platform
from core.domain.value_objects import InputData, TimePoint, UserProfile, BotSettings, PendingMessage
from core.domain.commands import SendReply
from ports.detection import DetectionResult

from core.pipeline.pipeline import Pipeline
from core.pipeline.stages import (
    GuardStage,
    AgingStage,
    DetectionStage,
    RegistrationStage,
    HydrationStage,
    FormatStage,
    CommandFactoryStage,
)
from core.services.dispatcher import MessageDispatcher

from tests.fakes.ports import FakeDetectionPort, FakeStoragePort, FakeCommandExecutorPort, FakePendingPort


def _make_fresh_pipeline(storage, detection):
    """Minimal fresh pipeline for dispatcher tests."""
    return Pipeline([
        GuardStage(),
        AgingStage(BotSettings()),
        DetectionStage(detection),
        RegistrationStage(storage),
        HydrationStage(storage),
        FormatStage(BotSettings()),
        CommandFactoryStage(),
    ])


def _make_replay_pipeline(storage):
    return Pipeline([
        HydrationStage(storage),
        FormatStage(BotSettings()),
        CommandFactoryStage(),
    ])


@pytest.mark.asyncio
async def test_dispatcher_routes_commands_to_correct_executor():
    # 1. Arrange
    storage = FakeStoragePort()
    tg_executor = FakeCommandExecutorPort()
    dc_executor = FakeCommandExecutorPort()

    user = UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/London", city="London", flag="🇬🇧")
    storage.users[(1, Platform.TELEGRAM)] = user
    storage.members[("chat1", Platform.TELEGRAM)] = [user]

    tp = TimePoint(time="12:00", tz_city=None)
    detection = FakeDetectionPort(time_mentioned=True, points=[tp])

    fresh = _make_fresh_pipeline(storage, detection)
    replay = _make_replay_pipeline(storage)

    dispatcher = MessageDispatcher(
        fresh_pipeline=fresh,
        replay_pipeline=replay,
        tg_executor=tg_executor,
        dc_executor=dc_executor,
    )

    # 2. Act
    data = InputData(
        text="Let's meet at 12:00",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="Alice",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1",
    )
    await dispatcher.process_input(data)

    # 3. Assert
    assert len(tg_executor.executed_commands) == 1
    assert isinstance(tg_executor.executed_commands[0], SendReply)
    assert len(dc_executor.executed_commands) == 0


@pytest.mark.asyncio
async def test_dispatcher_replay_uses_checkpoint_detection():
    """Replay pipeline uses ctx.detection from PendingMessage — no re-detection occurs.
    FakeDetectionPort is set to time_mentioned=False; if it were called, no reply would be produced.
    Since replay pipeline skips DetectionStage entirely, the cached detection is used → reply is sent.
    """
    storage = FakeStoragePort()
    tg_executor = FakeCommandExecutorPort()

    user = UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/London", city="London", flag="🇬🇧")
    storage.users[(1, Platform.TELEGRAM)] = user
    storage.members[("chat1", Platform.TELEGRAM)] = [user]

    # If detection were called, it would return no time → no reply. It should NOT be called.
    detection = FakeDetectionPort(time_mentioned=False, points=[])

    fresh = _make_fresh_pipeline(storage, detection)
    replay = _make_replay_pipeline(storage)

    dispatcher = MessageDispatcher(
        fresh_pipeline=fresh,
        replay_pipeline=replay,
        tg_executor=tg_executor,
        dc_executor=None,
    )

    original_data = InputData(
        text="I said 12:00 yesterday!",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="Alice",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1",
    )

    # Pre-built detection checkpoint (what was stored in PendingMessage)
    cached_detection = DetectionResult(
        time_mentioned=True,
        points=(TimePoint(time="12:00", tz_city=None),),
    )
    pending_msg = PendingMessage(original_input=original_data, detection=cached_detection)

    await dispatcher.process_pending(pending_msg)

    assert len(tg_executor.executed_commands) == 1
    assert isinstance(tg_executor.executed_commands[0], SendReply)
