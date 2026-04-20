import dataclasses
from datetime import datetime, timezone

import pytest

from core.domain.enums import Platform
from core.domain.value_objects import BotSettings, InputData, MessageContext, TimePoint, UserProfile
from core.pipeline.stages import DecisionStage, FormatStage, GeoResolveStage
from ports.detection import DetectionResult
from ports.geocoding import Location
from tests.fakes.ports import FakeGeoPort


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

    ctx = await DecisionStage().process(ctx)

    assert ctx.decision is not None
    assert ctx.decision.reply_text == "15:00 Berlin"
    assert ctx.decision.needs_onboarding is True
    assert ctx.decision.pending_message is not None
    assert ctx.decision.ignore is False


@pytest.mark.asyncio
async def test_decision_stage_onboarding_without_reply():
    ctx = _ctx()

    ctx = await DecisionStage().process(ctx)

    assert ctx.decision is not None
    assert ctx.decision.reply_text is None
    assert ctx.decision.pending_message is not None
    assert ctx.decision.needs_onboarding is True


@pytest.mark.asyncio
async def test_decision_stage_declined_user_gets_ignore_decision():
    ctx = _ctx(sender=UserProfile(user_id=1, platform=Platform.TELEGRAM, onboarding_declined=True))

    ctx = await DecisionStage().process(ctx)

    assert ctx.decision is not None
    assert ctx.decision.ignore is True


@pytest.mark.asyncio
async def test_decision_stage_configured_sender_with_reply_produces_no_onboarding():
    """sender with timezone + reply_text → needs_onboarding=False, ignore=False."""
    ctx = _ctx(
        sender=UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/Berlin"),
        reply_text="15:00 Berlin"
    )

    ctx = await DecisionStage().process(ctx)

    assert ctx.decision.needs_onboarding is False
    assert ctx.decision.ignore is False


@pytest.mark.asyncio
async def test_decision_stage_configured_sender_without_reply_produces_ignore():
    """sender with timezone, but reply_text=None (no matching members) → ignore=True."""
    ctx = _ctx(
        sender=UserProfile(user_id=1, platform=Platform.TELEGRAM, timezone="Europe/Berlin"),
        reply_text=None
    )

    ctx = await DecisionStage().process(ctx)

    assert ctx.decision.ignore is True


@pytest.mark.asyncio
async def test_format_stage_uses_tz_resolved_when_sender_has_no_timezone():
    """tz_resolved in TimePoint → FormatStage builds reply_text using it."""
    ctx = _ctx(sender=UserProfile(user_id=1, platform=Platform.TELEGRAM))
    # Add tz_resolved to one of the points
    new_points = (dataclasses.replace(ctx.detection.points[0], tz_resolved="Europe/London"),)
    ctx = dataclasses.replace(ctx, detection=dataclasses.replace(ctx.detection, points=new_points))

    ctx = await FormatStage(BotSettings()).process(ctx)

    assert ctx.reply_text is not None
    assert "London" in ctx.reply_text


@pytest.mark.asyncio
async def test_format_stage_returns_ctx_unchanged_when_no_source_tz():
    """No sender.timezone and no tz_resolved → reply_text remains None."""
    ctx = _ctx(sender=UserProfile(user_id=1, platform=Platform.TELEGRAM))
    
    ctx = await FormatStage(BotSettings()).process(ctx)

    assert ctx.reply_text is None


@pytest.mark.asyncio
async def test_geo_resolve_stage_resolves_tz_city():
    """If TimePoint has tz_city and no tz_resolved → Stage resolves it."""
    geo = FakeGeoPort(resolves_to=Location(city="London", timezone="Europe/London", country_code="GB"))
    stage = GeoResolveStage(geo)
    
    ctx = _ctx()
    new_points = (dataclasses.replace(ctx.detection.points[0], tz_city="London"),)
    ctx = dataclasses.replace(ctx, detection=dataclasses.replace(ctx.detection, points=new_points))

    ctx = await stage.process(ctx)

    assert ctx.detection.points[0].tz_resolved == "Europe/London"


@pytest.mark.asyncio
async def test_geo_resolve_stage_skips_already_resolved():
    """If tz_resolved is already set → Stage does not call GeoPort (skips)."""
    # FakeGeoPort resolves to Berlin, but if we skip, it should stay London
    geo = FakeGeoPort(resolves_to=Location(city="Berlin", timezone="Europe/Berlin", country_code="DE"))
    stage = GeoResolveStage(geo)
    
    ctx = _ctx()
    new_points = (dataclasses.replace(ctx.detection.points[0], tz_city="London", tz_resolved="Europe/London"),)
    ctx = dataclasses.replace(ctx, detection=dataclasses.replace(ctx.detection, points=new_points))

    ctx = await stage.process(ctx)

    assert ctx.detection.points[0].tz_resolved == "Europe/London"


@pytest.mark.asyncio
async def test_geo_resolve_stage_unknown_city_passes_through():
    """If GeoPort returns None → ctx unchanged, tz_city remains."""
    geo = FakeGeoPort(resolves_to=None)
    stage = GeoResolveStage(geo)
    
    ctx = _ctx()
    new_points = (dataclasses.replace(ctx.detection.points[0], tz_city="Unknown"),)
    ctx = dataclasses.replace(ctx, detection=dataclasses.replace(ctx.detection, points=new_points))

    ctx = await stage.process(ctx)

    assert ctx.detection.points[0].tz_city == "Unknown"
    assert ctx.detection.points[0].tz_resolved is None
