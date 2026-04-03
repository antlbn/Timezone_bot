"""Tests for formatter module."""

from unittest.mock import patch

from src.formatter import normalize_time, format_conversion_reply


class TestNormalizeTime:
    """Test normalize_time function."""

    # ============================================================
    # 12h to 24h conversion
    # ============================================================

    def test_pm_simple(self):
        """5 pm -> 17:00."""
        assert normalize_time("5 pm") == "17:00"

    def test_am_simple(self):
        """9 AM -> 09:00."""
        assert normalize_time("9 AM") == "09:00"

    def test_pm_with_minutes(self):
        """5:30 pm -> 17:30."""
        assert normalize_time("5:30 pm") == "17:30"

    def test_noon(self):
        """12 pm -> 12:00."""
        assert normalize_time("12 pm") == "12:00"

    def test_midnight(self):
        """12 am -> 00:00."""
        assert normalize_time("12 am") == "00:00"

    # ============================================================
    # 24h format (should stay the same)
    # ============================================================

    def test_24h_unchanged(self):
        """14:00 -> 14:00."""
        assert normalize_time("14:00") == "14:00"

    def test_24h_single_digit(self):
        """9:30 -> 09:30."""
        assert normalize_time("9:30") == "09:30"

    def test_24h_midnight(self):
        """00:00 -> 00:00."""
        assert normalize_time("00:00") == "00:00"

    # ============================================================
    # Edge cases
    # ============================================================

    def test_fallback_on_invalid(self):
        """Invalid input returns original string."""
        assert normalize_time("not a time") == "not a time"

    def test_case_insensitive(self):
        """AM/PM case insensitive."""
        assert normalize_time("5 PM") == "17:00"
        assert normalize_time("5 pM") == "17:00"


class TestFormatConversionReply:
    """Test format_conversion_reply function."""

    def test_single_user_no_groups(self):
        """Test with no other members."""
        with patch(
            "src.formatter.get_bot_settings",
            return_value={
                "display_limit_per_chat": 0,
                "show_usernames": False,
                "render_mode": "vertical",
                "show_sender_prefix": False,
            },
        ):
            reply = format_conversion_reply(
                original_time="14:00",
                sender_city="Berlin",
                sender_tz="Europe/Berlin",
                sender_flag="🇩🇪",
                members=[],
                sender_name="Alice",
            )
        assert "Alice:" not in reply
        assert "14:00" in reply
        assert "/tb_help" not in reply
        assert "|" not in reply

    def test_multiple_timezones(self):
        """Test with members in different timezones."""
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

        with patch(
            "src.formatter.get_bot_settings",
            return_value={
                "display_limit_per_chat": 0,
                "show_usernames": False,
                "render_mode": "vertical",
                "show_sender_prefix": False,
            },
        ):
            reply = format_conversion_reply(
                original_time="14:00",
                sender_city="Berlin",
                sender_tz="Europe/Berlin",
                sender_flag="🇩🇪",
                members=members,
                sender_name="Alice",
            )

        # 14:00 Berlin -> 08:00 NY (or 09:00 depending on DST), 22:00 Tokyo
        assert "Alice:" not in reply
        assert "14:00 Berlin 🇩🇪" in reply
        assert "New York 🇺🇸" in reply
        assert "Tokyo 🇯🇵" in reply
        assert "|" not in reply

    def test_day_offset(self):
        """Test day shift indicator (+1)."""
        # Berlin 23:00 -> Tokyo 07:00 next day
        members = [
            {
                "city": "Tokyo",
                "timezone": "Asia/Tokyo",
                "flag": "🇯🇵",
                "username": "charlie",
            }
        ]

        with patch(
            "src.formatter.get_bot_settings",
            return_value={
                "display_limit_per_chat": 0,
                "show_usernames": False,
                "render_mode": "vertical",
                "show_sender_prefix": False,
            },
        ):
            reply = format_conversion_reply(
                original_time="23:00",
                sender_city="Berlin",
                sender_tz="Europe/Berlin",
                sender_flag="🇩🇪",
                members=members,
            )

        # The actual time depends on DST, so we just check for the correct format/location
        assert "⁺¹ Tokyo 🇯🇵" in reply

    def test_mobile_wrapping(self):
        """Test that 3 locations result in 2 lines (2 + 1 wrapping)."""
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

        with patch(
            "src.formatter.get_bot_settings",
            return_value={
                "display_limit_per_chat": 0,
                "show_usernames": False,
                "render_mode": "vertical",
                "show_sender_prefix": False,
            },
        ):
            reply = format_conversion_reply(
                original_time="14:00",
                sender_city="Berlin",
                sender_tz="Europe/Berlin",
                sender_flag="🇩🇪",
                members=members,
                sender_name="Alice",
            )

        # Expected structure:
        # Alice:
        # 14:00 Berlin 🇩🇪 | 08:00 New York 🇺🇸
        # 22:00 Tokyo 🇯🇵
        lines = [line for line in reply.split("\n") if line.strip()]
        assert "14:00 Berlin 🇩🇪" in lines[0]
        assert "New York 🇺🇸" in lines[1]
        assert "Tokyo 🇯🇵" in lines[2]
        assert "|" not in "\n".join(lines)

    def test_compact_inline_render_mode(self):
        """Compact mode renders one point as a single inline sentence without flags."""
        members = [
            {
                "city": "Vienna",
                "timezone": "Europe/Vienna",
                "flag": "🇦🇹",
                "username": "bob",
            }
        ]

        with patch(
            "src.formatter.get_bot_settings",
            return_value={
                "display_limit_per_chat": 0,
                "show_usernames": False,
                "render_mode": "compact_inline",
                "compact_inline_monospace": False,
            },
        ):
            reply = format_conversion_reply(
                original_time="10:00",
                sender_city="Moscow",
                sender_tz="Europe/Moscow",
                sender_flag="🇷🇺",
                members=members,
                sender_name="Alice",
            )

        assert not reply.startswith("Alice: ")
        assert "Moscow" in reply
        assert "Vienna" in reply
        assert "🇷🇺" not in reply
        assert "🇦🇹" not in reply
        assert "\n" not in reply

    def test_sender_prefix_can_be_enabled_explicitly(self):
        """Sender prefix is shown only when enabled in settings."""
        with patch(
            "src.formatter.get_bot_settings",
            return_value={
                "display_limit_per_chat": 0,
                "show_usernames": False,
                "render_mode": "vertical",
                "show_sender_prefix": True,
            },
        ):
            reply = format_conversion_reply(
                original_time="14:00",
                sender_city="Berlin",
                sender_tz="Europe/Berlin",
                sender_flag="🇩🇪",
                members=[],
                sender_name="Alice",
            )

        assert reply.startswith("Alice: ")

    def test_compact_inline_multiple_points_and_footer(self):
        """Compact mode keeps points on separate lines and footer at the end."""
        from src.formatter import format_multi_conversion

        members = [
            {
                "city": "Vienna",
                "timezone": "Europe/Vienna",
                "flag": "🇦🇹",
                "username": "bob",
            }
        ]
        conversions = [
            {
                "original_time": "10:00",
                "source_city": "Moscow",
                "source_tz": "Europe/Moscow",
                "source_flag": "🇷🇺",
                "event_type": "deadline",
            },
            {
                "original_time": "15:00",
                "source_city": "Moscow",
                "source_tz": "Europe/Moscow",
                "source_flag": "🇷🇺",
                "event_type": "review",
            },
        ]

        with patch(
            "src.formatter.get_bot_settings",
            return_value={
                "display_limit_per_chat": 0,
                "show_usernames": False,
                "render_mode": "compact_inline",
                "compact_inline_monospace": False,
            },
        ):
            reply = format_multi_conversion(
                conversions=conversions,
                members=members,
                footer="updated time",
            )

        lines = reply.split("\n")
        assert lines[0].startswith("deadline at 10:00 Moscow")
        assert lines[1].startswith("review")
        assert "at 15:00 Moscow" in lines[1]
        assert lines[2] == "**updated time**"

    def test_compact_inline_aligns_time_column_by_longest_event_name(self):
        """Compact mode aligns the first time after the longest event label."""
        from src.formatter import format_multi_conversion

        conversions = [
            {
                "original_time": "10:00",
                "source_city": "Moscow",
                "source_tz": "Europe/Moscow",
                "source_flag": "🇷🇺",
                "event_type": "call",
            },
            {
                "original_time": "12:30",
                "source_city": "Moscow",
                "source_tz": "Europe/Moscow",
                "source_flag": "🇷🇺",
                "event_type": "very long deadline",
            },
        ]

        with patch(
            "src.formatter.get_bot_settings",
            return_value={
                "display_limit_per_chat": 0,
                "show_usernames": False,
                "render_mode": "compact_inline",
                "show_sender_prefix": False,
                "compact_inline_monospace": False,
            },
        ):
            reply = format_multi_conversion(conversions=conversions, members=[])

        lines = reply.split("\n")
        assert lines[0].index("at 10:00") == lines[1].index("at 12:30")

    def test_compact_inline_can_be_wrapped_in_monospace_block(self):
        """Compact inline mode can wrap the body in a code block for visual alignment."""
        from src.formatter import format_multi_conversion

        conversions = [
            {
                "original_time": "10:00",
                "source_city": "Moscow",
                "source_tz": "Europe/Moscow",
                "source_flag": "🇷🇺",
                "event_type": "call",
            },
            {
                "original_time": "12:30",
                "source_city": "Moscow",
                "source_tz": "Europe/Moscow",
                "source_flag": "🇷🇺",
                "event_type": "very long deadline",
            },
        ]

        with patch(
            "src.formatter.get_bot_settings",
            return_value={
                "display_limit_per_chat": 0,
                "show_usernames": False,
                "render_mode": "compact_inline",
                "show_sender_prefix": False,
                "compact_inline_monospace": True,
            },
        ):
            reply = format_multi_conversion(
                conversions=conversions,
                members=[],
                footer="updated time",
            )

        assert reply.startswith("```\n")
        assert "\n```\n**updated time**" in reply
