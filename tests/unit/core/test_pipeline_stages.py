from datetime import datetime, timezone

import pytest

from core.domain.enums import Platform
from core.domain.value_objects import InputData, MessageContext, TimePoint, UserProfile
from core.pipeline.stages import DecisionStage
from ports.detection import DetectionResult


def _ctx(
    *,
    reply_text: str | None = None,
    sender: UserProfile | None = None,
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
    )


@pytest.mark.asyncio
async def test_decision_stage_reply_and_onboarding_decision():
    ctx = _ctx(reply_text="15:00 Berlin")

    result = await DecisionStage().process(ctx)

    assert result.decision is not None
    assert result.decision.reply_text == "15:00 Berlin"
    assert result.decision.needs_onboarding is True
    assert result.decision.pending_message is not None
    assert result.decision.ignore is False


@pytest.mark.asyncio
async def test_decision_stage_reply_and_pending_without_prompt_flags():
    ctx = _ctx(reply_text="15:00 Berlin")

    result = await DecisionStage().process(ctx)

    assert result.decision is not None
    assert result.decision.reply_text == "15:00 Berlin"
    assert result.decision.pending_message is not None
    assert result.decision.show_onboarding is False


@pytest.mark.asyncio
async def test_decision_stage_onboarding_without_reply():
    ctx = _ctx()

    result = await DecisionStage().process(ctx)

    assert result.decision is not None
    assert result.decision.reply_text is None
    assert result.decision.pending_message is not None
    assert result.decision.needs_onboarding is True


@pytest.mark.asyncio
async def test_decision_stage_declined_user_gets_ignore_decision():
    ctx = _ctx(sender=UserProfile(user_id=1, platform=Platform.TELEGRAM, onboarding_declined=True))

    result = await DecisionStage().process(ctx)

    assert result.decision is not None
    assert result.decision.ignore is True
