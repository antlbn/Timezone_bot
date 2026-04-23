import pytest
from datetime import datetime, timezone, timedelta

from core.domain.enums import Platform
from core.domain.value_objects import InputData, MessageContext, TimePoint, UserProfile, BotSettings
from core.pipeline.pipeline import Pipeline
from core.pipeline.stages import (
    GuardStage, AgingStage, DetectionStage,
    HydrationStage, FormatStage, DecisionStage,
)
from tests.fakes.ports import FakeDetectionPort, FakeStoragePort, FakeTimePort


def _fresh_pipeline(storage, detection, settings=None, time_port=None):
    settings = settings or BotSettings()
    time_port = time_port or FakeTimePort()
    return Pipeline([
        GuardStage(settings),
        AgingStage(settings, time_port),
        DetectionStage(detection),
        HydrationStage(users_repo=storage, chats_repo=storage),
        FormatStage(settings),
        DecisionStage(),
    ])


@pytest.mark.asyncio
async def test_pipeline_no_time_noop():
    storage = FakeStoragePort()
    detection = FakeDetectionPort(time_mentioned=False)

    pipeline = _fresh_pipeline(storage, detection)

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
    assert ctx.stop_processing is True
    assert ctx.decision is None


@pytest.mark.asyncio
async def test_pipeline_time_found_configured_user_sends_reply():
    storage = FakeStoragePort()

    sender = UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/Berlin", city="Berlin", flag="🇩🇪")
    receiver = UserProfile(user_id=2, platform=Platform.TELEGRAM, timezone="America/New_York", city="New York", flag="🇺🇸")
    storage.users[(1, Platform.TELEGRAM)] = sender
    storage.members[("chat1", Platform.TELEGRAM)] = [receiver]

    tp = TimePoint(time="15:00", tz_city=None)
    detection = FakeDetectionPort(time_mentioned=True, points=[tp])
    pipeline = _fresh_pipeline(storage, detection)

    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="John",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1"
    ))

    ctx = await pipeline.run(ctx)

    assert ctx.stop_processing is False
    assert ctx.reply_text is not None
    assert "15:00 Berlin" in ctx.reply_text
    assert ctx.decision is not None
    assert ctx.decision.reply_text == ctx.reply_text
    assert ctx.decision.needs_onboarding is False


@pytest.mark.asyncio
async def test_pipeline_time_found_unconfigured_user_triggers_onboarding():
    """New user without timezone produces an onboarding decision."""
    storage = FakeStoragePort()

    tp = TimePoint(time="15:00", tz_city=None)
    detection = FakeDetectionPort(time_mentioned=True, points=[tp])
    pipeline = _fresh_pipeline(storage, detection)

    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="John",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1"
    ))

    ctx = await pipeline.run(ctx)

    assert ctx.stop_processing is False
    assert ctx.decision is not None
    assert ctx.decision.needs_onboarding is True
    assert ctx.decision.pending_message is not None
    assert ctx.decision.reply_text is None


@pytest.mark.asyncio
async def test_pipeline_declined_onboarding_no_spam():
    """User declined -> pipeline returns an ignore decision."""
    storage = FakeStoragePort()

    sender = UserProfile(user_id=1, platform=Platform.TELEGRAM, onboarding_declined=True)
    storage.users[(1, Platform.TELEGRAM)] = sender

    tp = TimePoint(time="15:00", tz_city=None)
    detection = FakeDetectionPort(time_mentioned=True, points=[tp])
    pipeline = _fresh_pipeline(storage, detection)

    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00", user_id=1, platform=Platform.TELEGRAM,
        author_name="John", timestamp_utc=datetime.now(timezone.utc), chat_id="chat1"
    ))

    ctx = await pipeline.run(ctx)

    assert ctx.stop_processing is False
    assert ctx.decision is not None
    assert ctx.decision.ignore is True


@pytest.mark.asyncio
async def test_pipeline_aging_stage_drops_old_messages():
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    time_port = FakeTimePort(now=now)
    pipeline = Pipeline([AgingStage(BotSettings(max_age_fresh_secs=30), time_port)])

    old_time = now - timedelta(minutes=10)
    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00", user_id=1, platform=Platform.TELEGRAM,
        author_name="John", timestamp_utc=old_time, chat_id="chat1"
    ))

    ctx = await pipeline.run(ctx)
    assert ctx.stop_processing is True


@pytest.mark.asyncio
async def test_pipeline_guard_stage_drops_bots():
    pipeline = Pipeline([GuardStage(BotSettings())])

    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00", user_id=1, platform=Platform.TELEGRAM,
        author_name="Bot", timestamp_utc=datetime.now(timezone.utc), chat_id="chat1",
        is_bot=True
    ))

    ctx = await pipeline.run(ctx)
    assert ctx.stop_processing is True


@pytest.mark.asyncio
async def test_pipeline_guard_stage_uses_configured_hard_skip_limit():
    pipeline = Pipeline([GuardStage(BotSettings(max_message_hard_skip_chars=5))])

    ctx = MessageContext(input=InputData(
        text="123456", user_id=1, platform=Platform.TELEGRAM,
        author_name="John", timestamp_utc=datetime.now(timezone.utc), chat_id="chat1"
    ))

    ctx = await pipeline.run(ctx)
    assert ctx.stop_processing is True


@pytest.mark.asyncio
async def test_pipeline_does_not_register_unknown_user_anymore():
    """Registration moved out of pipeline; pipeline itself remains read-heavy."""
    storage = FakeStoragePort()

    tp = TimePoint(time="15:00", tz_city=None)
    detection = FakeDetectionPort(time_mentioned=True, points=[tp])
    pipeline = _fresh_pipeline(storage, detection)

    ctx = MessageContext(input=InputData(
        text="Meeting at 15:00", user_id=42, platform=Platform.TELEGRAM,
        author_name="Alice", timestamp_utc=datetime.now(timezone.utc), chat_id="chat1"
    ))
    await pipeline.run(ctx)

    assert (42, Platform.TELEGRAM, "Alice") not in storage.created


@pytest.mark.asyncio
async def test_tz_resolved_bypasses_onboarding_for_declined_user():
    """Declined user who writes '14:00 по Лондону' should receive a SendReply.
    Decline blocks onboarding even when a reply can be built from tz_resolved.
    """
    storage = FakeStoragePort()

    declined = UserProfile(user_id=1, platform=Platform.TELEGRAM, onboarding_declined=True)
    storage.users[(1, Platform.TELEGRAM)] = declined

    tp = TimePoint(time="14:00", tz_city="London", tz_resolved="Europe/London")
    detection = FakeDetectionPort(time_mentioned=True, points=[tp])
    pipeline = _fresh_pipeline(storage, detection)

    ctx = MessageContext(input=InputData(
        text="14:00 по Лондону", user_id=1, platform=Platform.TELEGRAM,
        author_name="John", timestamp_utc=datetime.now(timezone.utc), chat_id="chat1"
    ))
    ctx = await pipeline.run(ctx)

    assert ctx.decision is not None
    assert ctx.decision.reply_text is not None
    assert ctx.decision.needs_onboarding is False
