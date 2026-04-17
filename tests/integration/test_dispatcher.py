import pytest
from datetime import datetime, timezone

from src.core.domain.enums import Platform
from src.core.domain.value_objects import InputData, TimePoint, UserProfile, BotSettings, PendingMessage
from src.core.domain.commands import SendReply

from src.core.pipeline.pipeline import Pipeline
from src.core.pipeline.stages import GuardStage, AgingStage, DetectionStage, ResolveStage, FormatStage, CommandFactoryStage
from src.core.services.dispatcher import MessageDispatcher

from tests.fakes.ports import FakeDetectionPort, FakeStoragePort, FakeCommandExecutorPort

@pytest.mark.asyncio
async def test_dispatcher_routes_commands_to_correct_executor():
    # 1. Arrange: Setup Fakes
    storage = FakeStoragePort()
    tg_executor = FakeCommandExecutorPort()
    dc_executor = FakeCommandExecutorPort()
    
    # User exists and is in a chat
    user = UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/London", city="London", flag="🇬🇧")
    storage.users[(1, Platform.TELEGRAM)] = user
    storage.members[("chat1", Platform.TELEGRAM)] = [user]

    tp = TimePoint(time="12:00", tz_city=None)
    detection = FakeDetectionPort(time_mentioned=True, points=[tp])
    
    pipeline = Pipeline([
        GuardStage(),
        AgingStage(max_age_seconds=120),
        DetectionStage(detection),
        ResolveStage(storage),
        FormatStage(BotSettings()),
        CommandFactoryStage()
    ])

    dispatcher = MessageDispatcher(
        pipeline=pipeline,
        tg_executor=tg_executor,
        dc_executor=dc_executor
    )

    # 2. Act: Send message from Telegram
    data = InputData(
        text="Let's meet at 12:00",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="Alice",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1"
    )
    await dispatcher.process_input(data)

    # 3. Assert: Telegram executor got the command, Discord didn't
    assert len(tg_executor.executed_commands) == 1
    assert isinstance(tg_executor.executed_commands[0], SendReply)
    assert len(dc_executor.executed_commands) == 0

@pytest.mark.asyncio
async def test_dispatcher_from_pending_skips_detection_and_uses_cached_result():
    # 1. Arrange
    storage = FakeStoragePort()
    tg_executor = FakeCommandExecutorPort()
    
    # The user was just onboarded
    user = UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/London", city="London", flag="🇬🇧")
    storage.users[(1, Platform.TELEGRAM)] = user
    storage.members[("chat1", Platform.TELEGRAM)] = [user]

    # VERY IMPORTANT: Detection Fake is set to False! It should NOT find a time.
    # If the pipeline calls this fake, the test will fail by returning NoOp.
    detection = FakeDetectionPort(time_mentioned=False, points=[])
    
    pipeline = Pipeline([
        GuardStage(),
        AgingStage(max_age_seconds=120),
        DetectionStage(detection),
        ResolveStage(storage),
        FormatStage(BotSettings()),
        CommandFactoryStage()
    ])

    dispatcher = MessageDispatcher(
        pipeline=pipeline,
        tg_executor=tg_executor,
        dc_executor=None
    )

    # Act: Replay a message from pending
    original_data = InputData(
        text="I said 12:00 yesterday!",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="Alice",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1"
    )
    
    from src.ports.detection import DetectionResult
    cached_result = DetectionResult(time_mentioned=True, points=(TimePoint(time="12:00", tz_city=None),))
    pending_msg = PendingMessage(original_input=original_data, detection=cached_result)
    
    # process_pending uses the cached result
    await dispatcher.process_pending(pending_msg)

    # 3. Assert
    # If it hit the Fake Detection, time_mentioned would be False and NO reply would be sent.
    # Since it bypassed it, it formatted a reply!
    assert len(tg_executor.executed_commands) == 1
    assert isinstance(tg_executor.executed_commands[0], SendReply)
