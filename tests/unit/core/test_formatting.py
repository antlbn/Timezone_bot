import pytest
from datetime import datetime, timezone

from core.domain.enums import Platform, ResponseStyle
from core.domain.value_objects import TimePoint, UserProfile
from core.services.formatting import (
    _format_time_with_shift,
    format_multi_conversion,
    format_single_point,
)


@pytest.fixture
def sender():
    return UserProfile(
        user_id=1,
        platform=Platform.TELEGRAM,
        username="alice",
        city="Berlin",
        timezone="Europe/Berlin",
        flag="🇩🇪",
    )


@pytest.fixture
def members():
    return [
        UserProfile(
            user_id=2,
            platform=Platform.TELEGRAM,
            username="bob",
            city="New York",
            timezone="America/New_York",
            flag="🇺🇸",
        ),
        UserProfile(
            user_id=3,
            platform=Platform.TELEGRAM,
            username="carol",
            city="Tokyo",
            timezone="Asia/Tokyo",
            flag="🇯🇵",
        ),
    ]


def test_format_time_with_shift():
    assert _format_time_with_shift("15:00", 0) == "15:00"
    assert _format_time_with_shift("15:00", 1) == "15:00⁺¹"
    assert _format_time_with_shift("15:00", -1) == "15:00⁻¹"


def test_format_single_point_block(sender, members):
    point = TimePoint(time="15:00", event_title="Meeting")
    result = format_single_point(point, sender, members, ResponseStyle.BLOCK, True, True, reference_date=datetime.now(timezone.utc))

    assert "Meeting" in result
    assert "15:00 Berlin 🇩🇪" in result
    assert "@bob" in result or "@carol" in result


def test_format_multi_conversion_inline(sender, members):
    points = (
        TimePoint(time="15:00", event_title="Call"),
        TimePoint(time="16:30"),
    )
    result = format_multi_conversion(
        points,
        sender,
        members,
        response_style=ResponseStyle.INLINE,
        show_usernames=False,
        show_event_title=True,
        reference_date=datetime.now(timezone.utc),
    )

    assert result.startswith("It is")
    assert "Call" in result
    assert "15:00 Berlin" in result
    assert "16:30 Berlin" in result


def test_format_multi_conversion_no_points(sender, members):
    assert format_multi_conversion((), sender, members) == ""


def test_format_single_point_ambiguous(sender, members):
    point = TimePoint(time="03:00".replace("03", "03"), am_pm_clear=False)
    result = format_single_point(point, sender, members, ResponseStyle.BLOCK, False, False, reference_date=datetime.now(timezone.utc))

    assert result.startswith("AM/PM?")
