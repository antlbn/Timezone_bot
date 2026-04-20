from datetime import datetime, timezone
import dataclasses
import pytest
from dataclasses import FrozenInstanceError
from core.domain.enums import Platform
from core.domain.value_objects import InputData, MessageContext, TimePoint


def test_timepoint_validation_valid():
    """Test valid time format -> OK."""
    tp = TimePoint(time="15:30")
    assert tp.time == "15:30"


def test_timepoint_validation_invalid():
    """Bad time format -> ValueError."""
    with pytest.raises(ValueError):
        TimePoint(time="25:99")
    with pytest.raises(ValueError):
        TimePoint(time="hello")


def test_timepoint_is_frozen():
    """TimePoint is immutable."""
    tp = TimePoint(time="10:00")
    with pytest.raises(FrozenInstanceError):
        tp.time = "11:00"


def test_message_context_is_frozen():
    """MessageContext is immutable."""
    ctx = MessageContext(
        input=InputData(
            text="test",
            user_id=1,
            platform=Platform.TELEGRAM,
            author_name="test",
            timestamp_utc=datetime.now(timezone.utc),
            chat_id="chat1",
        )
    )
    with pytest.raises(FrozenInstanceError):
        ctx.reply_text = "new text"


def test_message_context_replace_returns_new_instance():
    """dataclasses.replace returns a new instance of MessageContext."""
    ctx = MessageContext(
        input=InputData(
            text="test",
            user_id=1,
            platform=Platform.TELEGRAM,
            author_name="test",
            timestamp_utc=datetime.now(timezone.utc),
            chat_id="chat1",
        )
    )
    new_ctx = dataclasses.replace(ctx, reply_text="formatted")

    assert new_ctx is not ctx
    assert new_ctx.reply_text == "formatted"
    assert ctx.reply_text is None
