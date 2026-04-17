import pytest
from datetime import datetime, timezone
from src.core.domain.enums import Platform
from src.core.domain.value_objects import InputData, MessageContext, TimePoint, UserProfile, BotSettings
from src.core.domain.commands import SendReply, ShowOnboarding, SavePending, NoOp
from src.core.pipeline.pipeline import Pipeline
from src.core.pipeline.stages import GuardStage, AgingStage, DetectionStage, ResolveStage, FormatStage, CommandFactoryStage
from tests.fakes.ports import FakeDetectionPort, FakeStoragePort

@pytest.mark.asyncio
async def test_pipeline_no_time_noop():
    storage = FakeStoragePort()
    detection = FakeDetectionPort(time_mentioned=False)
    
    settings = BotSettings()
    pipeline = Pipeline([
        GuardStage(),
        AgingStage(max_age_seconds=120),
        DetectionStage(detection),
        ResolveStage(storage),
        FormatStage(settings),
        CommandFactoryStage()
    ])

    sender = UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/Berlin", city="Berlin", flag="🇩🇪")
    storage.users[(1, Platform.TELEGRAM)] = sender
    
    ctx = MessageContext(input=InputData(
        text="Hello world!",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="John",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1"
    ))

    ctx = await pipeline.run(ctx)
    commands = ctx.commands
    
    assert ctx._stopped is True
    assert len(commands) == 0

@pytest.mark.asyncio
async def test_pipeline_time_found_configured_user_sends_reply():
    storage = FakeStoragePort()
    
    receiver = UserProfile(user_id=2, platform=Platform.TELEGRAM, timezone="America/New_York", city="New York", flag="🇺🇸")
    storage.members[("chat1", Platform.TELEGRAM)] = [receiver]

    tp = TimePoint(time="15:00", tz_city=None)
    detection = FakeDetectionPort(time_mentioned=True, points=[tp])
    
    settings = BotSettings()
    pipeline = Pipeline([
        GuardStage(),
        AgingStage(max_age_seconds=120),
        DetectionStage(detection),
        ResolveStage(storage),
        FormatStage(settings),
        CommandFactoryStage()
    ])

    sender = UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/Berlin", city="Berlin", flag="🇩🇪")
    storage.users[(1, Platform.TELEGRAM)] = sender
    
    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="John",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1"
    ))

    ctx = await pipeline.run(ctx)
    commands = ctx.commands
    
    assert ctx._stopped is False
    assert ctx.reply_text is not None
    assert "15:00 Berlin" in ctx.reply_text
    assert "09:00 New York" in ctx.reply_text or "10:00 New York" in ctx.reply_text # Depends on DST

    assert len(commands) == 1
    assert isinstance(commands[0], SendReply)
    assert ctx.reply_text in commands[0].text

@pytest.mark.asyncio
async def test_pipeline_time_found_unconfigured_user_onboarding():
    storage = FakeStoragePort()
    tp = TimePoint(time="15:00", tz_city=None)
    detection = FakeDetectionPort(time_mentioned=True, points=[tp])
    
    settings = BotSettings()
    pipeline = Pipeline([
        GuardStage(),
        AgingStage(max_age_seconds=120),
        DetectionStage(detection),
        ResolveStage(storage),
        FormatStage(settings),
        CommandFactoryStage()
    ])

    # User is unconfigured
    
    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="John",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1"
    ))

    ctx = await pipeline.run(ctx)
    commands = ctx.commands
    
    assert ctx._stopped is False
    assert len(commands) == 2
    assert isinstance(commands[0], SavePending)
    assert isinstance(commands[1], ShowOnboarding)

@pytest.mark.asyncio
async def test_pipeline_declined_onboarding_no_spam():
    storage = FakeStoragePort()
    
    # User has declined onboarding!
    sender = UserProfile(user_id=1, platform=Platform.TELEGRAM, onboarding_declined=True)
    storage.users[(1, Platform.TELEGRAM)] = sender

    tp = TimePoint(time="15:00", tz_city=None)
    detection = FakeDetectionPort(time_mentioned=True, points=[tp])
    
    settings = BotSettings()
    pipeline = Pipeline([
        GuardStage(), AgingStage(max_age_seconds=120),
        DetectionStage(detection), ResolveStage(storage),
        FormatStage(settings), CommandFactoryStage()
    ])

    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00", user_id=1, platform=Platform.TELEGRAM,
        author_name="John", timestamp_utc=datetime.now(timezone.utc), chat_id="chat1"
    ))

    ctx = await pipeline.run(ctx)
    
    # Assert nothing is sent! No onboarding spam. (It yields NoOp)
    assert len(ctx.commands) == 1
    assert isinstance(ctx.commands[0], NoOp)

@pytest.mark.asyncio
async def test_pipeline_aging_stage_drops_old_messages():
    pipeline = Pipeline([AgingStage(max_age_seconds=120)])

    # Message is 10 minutes old!
    from datetime import timedelta
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    
    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00", user_id=1, platform=Platform.TELEGRAM,
        author_name="John", timestamp_utc=old_time, chat_id="chat1"
    ))

    ctx = await pipeline.run(ctx)
    
    # The aging stage stops the pipeline immediately
    assert ctx._stopped is True

@pytest.mark.asyncio
async def test_pipeline_guard_stage_drops_bots():
    pipeline = Pipeline([GuardStage()])
    
    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00", user_id=1, platform=Platform.TELEGRAM,
        author_name="Bot", timestamp_utc=datetime.now(timezone.utc), chat_id="chat1",
        is_bot=True # TRAP
    ))

    ctx = await pipeline.run(ctx)
    
    assert ctx._stopped is True
