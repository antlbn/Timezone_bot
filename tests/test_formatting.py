import pytest
from core.domain.value_objects import TimePoint, UserProfile
from core.domain.enums import Platform, ResponseStyle
from core.services.formatting import format_multi_conversion, format_single_point, _format_time_with_shift

@pytest.fixture
def sender():
    return UserProfile(
        user_id=1,
        platform=Platform.TELEGRAM,
        timezone="America/New_York",
        city="New York",
        flag="🇺🇸"
    )

@pytest.fixture
def members():
    return [
        UserProfile(user_id=2, platform=Platform.TELEGRAM, timezone="Europe/London", city="London", flag="🇬🇧"),
        UserProfile(user_id=3, platform=Platform.TELEGRAM, timezone="Asia/Tokyo", city="Tokyo", flag="🇯🇵"),
        UserProfile(user_id=4, platform=Platform.TELEGRAM, timezone="America/New_York", city="New York", flag="🇺🇸")
    ]

def test_format_time_with_shift():
    assert _format_time_with_shift("15:30", 0) == "15:30"
    assert _format_time_with_shift("15:30", 1) == "15:30⁺¹"
    assert _format_time_with_shift("15:30", -1) == "15:30⁻¹"

def test_format_single_point_block(sender, members):
    point = TimePoint(time="15:00", am_pm_clear=True)
    result = format_single_point(
        point=point,
        sender=sender,
        members=members,
        response_style=ResponseStyle.BLOCK,
        show_usernames=False,
        show_event_title=False
    )
    
    # 15:00 in NY is:
    # 20:00 in London (no shift if depending on summer time, let's assume conversion gives it)
    # The output should have lines for each. We don't strictly assert the hour because it depends on daylight saving
    # but we assert string format structure.
    assert "15:00 New York 🇺🇸" in result
    assert "London 🇬🇧" in result
    assert "Tokyo 🇯🇵" in result

def test_format_multi_conversion_inline(sender, members):
    points = (
        TimePoint(time="10:00", am_pm_clear=True),
        TimePoint(time="14:00", am_pm_clear=False)
    )
    result = format_multi_conversion(
        points=points,
        sender=sender,
        members=members,
        response_style=ResponseStyle.INLINE,
        show_usernames=False,
        show_event_title=False
    )
    
    assert "It is" in result
    assert "10:00 New York" in result
    assert "AM/PM?" in result # for 14:00 point

def test_format_multi_conversion_no_points(sender, members):
    assert format_multi_conversion((), sender, members) == ""

def test_format_single_point_ambiguous(sender, members):
    point = TimePoint(time="03:00", am_pm_clear=False)
    result = format_single_point(
        point=point,
        sender=sender,
        members=members,
        response_style=ResponseStyle.BLOCK,
        show_usernames=False,
        show_event_title=False
    )
    
    # The AM/PM? prefix should only appear on the source timezone (first line)
    lines = result.split("\n")
    assert "AM/PM?" in lines[0]
    assert "AM/PM?" not in lines[1]
