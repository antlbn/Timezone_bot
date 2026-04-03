"""Tests for formatter module."""

from unittest.mock import patch

import pytest

from src.formatter import (
    format_conversion_reply,
    format_multi_conversion,
    normalize_time,
)


@pytest.fixture(autouse=True)
def formatter_config_defaults():
    with (
        patch("src.formatter.get_response_style", return_value="block"),
        patch("src.formatter.get_show_event_title", return_value=False),
        patch("src.formatter.get_show_usernames", return_value=False),
    ):
        yield


class TestNormalizeTime:
    def test_pm_simple(self):
        assert normalize_time("5 pm") == "17:00"

    def test_am_simple(self):
        assert normalize_time("9 AM") == "09:00"

    def test_pm_with_minutes(self):
        assert normalize_time("5:30 pm") == "17:30"

    def test_noon(self):
        assert normalize_time("12 pm") == "12:00"

    def test_midnight(self):
        assert normalize_time("12 am") == "00:00"

    def test_24h_unchanged(self):
        assert normalize_time("14:00") == "14:00"

    def test_24h_single_digit(self):
        assert normalize_time("9:30") == "09:30"

    def test_fallback_on_invalid(self):
        assert normalize_time("not a time") == "not a time"


class TestFormatConversionReply:
    def test_single_user_no_groups(self):
        reply = format_conversion_reply(
            original_time="14:00",
            sender_city="Berlin",
            sender_tz="Europe/Berlin",
            sender_flag="🇩🇪",
            members=[],
            sender_name="Alice",
        )
        assert reply == "14:00 Berlin 🇩🇪"

    def test_multiple_timezones_source_first(self):
        members = [
            {
                "city": "New York",
                "timezone": "America/New_York",
                "flag": "🇺🇸",
                "username": "bob",
            },
            {
                "city": "Tokyo",
                "timezone": "Asia/Tokyo",
                "flag": "🇯🇵",
                "username": "charlie",
            },
        ]

        reply = format_conversion_reply(
            original_time="14:00",
            sender_city="Berlin",
            sender_tz="Europe/Berlin",
            sender_flag="🇩🇪",
            members=members,
            sender_name="Alice",
        )

        lines = reply.split("\n")
        assert lines[0] == "14:00 Berlin 🇩🇪"
        assert "New York 🇺🇸" in lines[1]
        assert "Tokyo 🇯🇵" in lines[2]
        assert "Alice:" not in reply
        assert "/tb_help" not in reply

    def test_day_offset(self):
        members = [
            {
                "city": "Tokyo",
                "timezone": "Asia/Tokyo",
                "flag": "🇯🇵",
                "username": "charlie",
            }
        ]

        reply = format_conversion_reply(
            original_time="23:00",
            sender_city="Berlin",
            sender_tz="Europe/Berlin",
            sender_flag="🇩🇪",
            members=members,
        )

        assert "06:00⁺¹ Tokyo 🇯🇵" in reply

    def test_grouping_by_timezone_joins_city_labels(self):
        members = [
            {
                "city": "Berlin",
                "timezone": "Europe/Berlin",
                "flag": "🇩🇪",
                "username": "alice",
            },
            {
                "city": "Munich",
                "timezone": "Europe/Berlin",
                "flag": "🇩🇪",
                "display_name": "Bob Smith",
            },
        ]

        with patch("src.formatter.get_show_usernames", return_value=True):
            reply = format_conversion_reply(
                original_time="14:00",
                sender_city="Berlin",
                sender_tz="Europe/Berlin",
                sender_flag="🇩🇪",
                members=members,
            )

        assert reply == "14:00 Berlin, Munich 🇩🇪 @alice, Bob Smith"

    def test_show_event_title_per_block_when_enabled(self):
        conversions = [
            {
                "original_time": "10:30",
                "source_city": "Sarajevo",
                "source_tz": "Europe/Sarajevo",
                "source_flag": "🇧🇦",
                "event_title": "Deadline",
                "am_pm_clear": True,
            }
        ]
        members = [
            {
                "city": "London",
                "timezone": "Europe/London",
                "flag": "🇬🇧",
                "username": "jane",
            }
        ]

        with patch("src.formatter.get_show_event_title", return_value=True):
            reply = format_multi_conversion(conversions, members)

        lines = reply.split("\n")
        assert lines[0] == "Deadline"
        assert lines[1] == "10:30 Sarajevo 🇧🇦"

    def test_ambiguous_prefix_added_to_source_line(self):
        conversions = [
            {
                "original_time": "08:00",
                "source_city": "Sarajevo",
                "source_tz": "Europe/Sarajevo",
                "source_flag": "🇧🇦",
                "am_pm_clear": False,
            }
        ]

        reply = format_multi_conversion(conversions, [])

        assert reply == "AM/PM? 08:00 Sarajevo 🇧🇦"

    def test_inline_sentence_style_has_compact_no_emoji_layout(self):
        conversions = [
            {
                "original_time": "10:30",
                "source_city": "Amsterdam",
                "source_tz": "Europe/Amsterdam",
                "source_flag": "🇳🇱",
                "event_title": "Standup",
                "am_pm_clear": True,
            }
        ]
        members = [
            {
                "city": "Cyprus",
                "timezone": "Asia/Nicosia",
                "flag": "🇨🇾",
                "username": "bob",
            },
            {
                "city": "Yerevan",
                "timezone": "Asia/Yerevan",
                "flag": "🇦🇲",
                "username": "charlie",
            },
        ]

        with (
            patch("src.formatter.get_response_style", return_value="inline_sentence"),
            patch("src.formatter.get_show_event_title", return_value=False),
        ):
            reply = format_multi_conversion(conversions, members)

        assert reply == "It is 10:30 Amsterdam, 11:30 Cyprus, 12:30 Yerevan"

    def test_inline_sentence_style_multiple_points_share_single_header(self):
        conversions = [
            {
                "original_time": "10:30",
                "source_city": "London",
                "source_tz": "Europe/London",
                "source_flag": "🇬🇧",
                "am_pm_clear": True,
            },
            {
                "original_time": "15:00",
                "source_city": "London",
                "source_tz": "Europe/London",
                "source_flag": "🇬🇧",
                "am_pm_clear": True,
            },
        ]
        members = [
            {
                "city": "Berlin",
                "timezone": "Europe/Berlin",
                "flag": "🇩🇪",
                "username": "bob",
            },
        ]

        with (
            patch("src.formatter.get_response_style", return_value="inline_sentence"),
            patch("src.formatter.get_show_event_title", return_value=False),
            patch("src.formatter.get_show_usernames", return_value=True),
        ):
            reply = format_multi_conversion(conversions, members)

        assert reply == "It is\n10:30 London, 11:30 Berlin\n15:00 London, 16:00 Berlin"

    def test_inline_sentence_style_shows_event_title_when_enabled(self):
        conversions = [
            {
                "original_time": "10:30",
                "source_city": "Amsterdam",
                "source_tz": "Europe/Amsterdam",
                "source_flag": "🇳🇱",
                "event_title": "Standup",
                "am_pm_clear": True,
            }
        ]

        with (
            patch("src.formatter.get_response_style", return_value="inline_sentence"),
            patch("src.formatter.get_show_event_title", return_value=True),
        ):
            reply = format_multi_conversion(conversions, [])

        assert reply == "Standup\n10:30 Amsterdam"

    def test_inline_sentence_style_multiple_titles_have_no_blank_line_between_points(
        self,
    ):
        conversions = [
            {
                "original_time": "10:30",
                "source_city": "London",
                "source_tz": "Europe/London",
                "source_flag": "🇬🇧",
                "event_title": "Standup",
                "am_pm_clear": True,
            },
            {
                "original_time": "15:00",
                "source_city": "London",
                "source_tz": "Europe/London",
                "source_flag": "🇬🇧",
                "event_title": "Retro",
                "am_pm_clear": True,
            },
        ]
        members = [
            {
                "city": "Berlin",
                "timezone": "Europe/Berlin",
                "flag": "🇩🇪",
                "username": "bob",
            },
        ]

        with (
            patch("src.formatter.get_response_style", return_value="inline_sentence"),
            patch("src.formatter.get_show_event_title", return_value=True),
        ):
            reply = format_multi_conversion(conversions, members)

        assert (
            reply
            == "Standup\n10:30 London, 11:30 Berlin\nRetro\n15:00 London, 16:00 Berlin"
        )

    def test_inline_sentence_style_keeps_ambiguous_prefix(self):
        conversions = [
            {
                "original_time": "08:00",
                "source_city": "Amsterdam",
                "source_tz": "Europe/Amsterdam",
                "source_flag": "🇳🇱",
                "am_pm_clear": False,
            }
        ]

        with (
            patch("src.formatter.get_response_style", return_value="inline_sentence"),
            patch("src.formatter.get_show_event_title", return_value=False),
        ):
            reply = format_multi_conversion(conversions, [])

        assert reply == "It is AM/PM? 08:00 Amsterdam"

    def test_name_list_truncation(self):
        members = [
            {
                "city": "Berlin",
                "timezone": "Europe/Berlin",
                "flag": "🇩🇪",
                "username": "alice",
            },
            {
                "city": "Munich",
                "timezone": "Europe/Berlin",
                "flag": "🇩🇪",
                "display_name": "Bob Smith",
            },
            {
                "city": "Hamburg",
                "timezone": "Europe/Berlin",
                "flag": "🇩🇪",
                "display_name": "Carol",
            },
            {
                "city": "Cologne",
                "timezone": "Europe/Berlin",
                "flag": "🇩🇪",
                "display_name": "Dave",
            },
        ]

        with patch("src.formatter.get_show_usernames", return_value=True):
            reply = format_conversion_reply(
                original_time="14:00",
                sender_city="Berlin",
                sender_tz="Europe/Berlin",
                sender_flag="🇩🇪",
                members=members,
            )

        assert "@alice" in reply
        assert "Bob Smith" in reply
        assert "+2 more" in reply
