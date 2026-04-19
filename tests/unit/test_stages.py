from datetime import datetime, timezone

import pytest

from core.domain.commands import (
    MarkOnboardingPromptShown,
    NoOp,
    SaveOnboardingPending,
    SendReply,
    ShowOnboarding,
)
from core.domain.enums import Platform
from core.domain.value_objects import BotSettings, InputData, MessageContext, TimePoint, UserProfile
from core.pipeline.stages import CommandFactoryStage, OnboardingChilloutStage
from ports.detection import DetectionResult
from tests.fakes.ports import FakeOnboardingChilloutStatePort


def _ctx(
    *,
    reply_text: str | None = None,
    sender: UserProfile | None = None,
    suppressed: bool = False,
) -> MessageContext:
    return MessageContext(
        input=InputData(
            text="Meeting at 15:00",
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
        sender=sender,
        reply_text=reply_text,
        onboarding_prompt_suppressed=suppressed,
    )


@pytest.mark.asyncio
async def test_command_factory_reply_and_onboarding_commands():
    ctx = _ctx(reply_text="15:00 Berlin")

    result = await CommandFactoryStage().process(ctx)

    assert [type(cmd) for cmd in result.commands] == [
        SendReply,
        SaveOnboardingPending,
        ShowOnboarding,
        MarkOnboardingPromptShown,
    ]


@pytest.mark.asyncio
async def test_command_factory_reply_and_pending_without_prompt_during_chillout():
    ctx = _ctx(reply_text="15:00 Berlin", suppressed=True)

    result = await CommandFactoryStage().process(ctx)

    assert [type(cmd) for cmd in result.commands] == [
        SendReply,
        SaveOnboardingPending,
    ]


@pytest.mark.asyncio
async def test_command_factory_onboarding_without_reply():
    ctx = _ctx()

    result = await CommandFactoryStage().process(ctx)

    assert [type(cmd) for cmd in result.commands] == [
        SaveOnboardingPending,
        ShowOnboarding,
        MarkOnboardingPromptShown,
    ]


@pytest.mark.asyncio
async def test_command_factory_declined_user_gets_no_onboarding_commands():
    ctx = _ctx(sender=UserProfile(user_id=1, platform=Platform.TELEGRAM, onboarding_declined=True))

    result = await CommandFactoryStage().process(ctx)

    assert len(result.commands) == 1
    assert isinstance(result.commands[0], NoOp)


@pytest.mark.asyncio
async def test_onboarding_chillout_stage_skips_check_when_timezone_exists():
    port = FakeOnboardingChilloutStatePort(in_chillout=True)
    stage = OnboardingChilloutStage(port, BotSettings(onboarding_cooldown_secs=600))
    ctx = _ctx(sender=UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/Berlin"))

    result = await stage.process(ctx)

    assert result.onboarding_prompt_suppressed is False
    assert port.checked == []


@pytest.mark.asyncio
async def test_onboarding_chillout_stage_skips_check_when_declined():
    port = FakeOnboardingChilloutStatePort(in_chillout=True)
    stage = OnboardingChilloutStage(port, BotSettings(onboarding_cooldown_secs=600))
    ctx = _ctx(sender=UserProfile(user_id=1, platform=Platform.TELEGRAM, onboarding_declined=True))

    result = await stage.process(ctx)

    assert result.onboarding_prompt_suppressed is False
    assert port.checked == []


@pytest.mark.asyncio
async def test_onboarding_chillout_stage_sets_suppressed_when_cooldown_active():
    port = FakeOnboardingChilloutStatePort(in_chillout=True)
    stage = OnboardingChilloutStage(port, BotSettings(onboarding_cooldown_secs=600))

    result = await stage.process(_ctx())

    assert result.onboarding_prompt_suppressed is True
    assert port.checked == [(1, Platform.TELEGRAM, 600)]


@pytest.mark.asyncio
async def test_onboarding_chillout_stage_leaves_prompt_enabled_when_no_cooldown():
    port = FakeOnboardingChilloutStatePort(in_chillout=False)
    stage = OnboardingChilloutStage(port, BotSettings(onboarding_cooldown_secs=600))

    result = await stage.process(_ctx())

    assert result.onboarding_prompt_suppressed is False
