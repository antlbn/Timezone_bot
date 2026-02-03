"""Tests for formatter module."""
import pytest
from src.formatter import normalize_time


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

from src.formatter import format_conversion_reply

class TestFormatConversionReply:
    """Test format_conversion_reply function."""

    def test_single_user_no_groups(self):
        """Test with no other members."""
        reply = format_conversion_reply(
            original_time="14:00",
            sender_city="Berlin",
            sender_tz="Europe/Berlin",
            sender_flag="🇩🇪",
            members=[],
            sender_name="Alice"
        )
        assert "Alice: 14:00 Berlin 🇩🇪" in reply
        assert "/tb_help" in reply
        assert "|" not in reply

    def test_multiple_timezones(self):
        """Test with members in different timezones."""
        members = [
            {"city": "New York", "timezone": "America/New_York", "flag": "🇺🇸", "username": "bob"},
            {"city": "Tokyo", "timezone": "Asia/Tokyo", "flag": "🇯🇵", "username": "charlie"}
        ]
        
        reply = format_conversion_reply(
            original_time="14:00",
            sender_city="Berlin",
            sender_tz="Europe/Berlin",
            sender_flag="🇩🇪",
            members=members,
            sender_name="Alice"
        )
        
        # 14:00 Berlin -> 08:00 NY, 22:00 Tokyo
        assert "Alice: 14:00 Berlin 🇩🇪" in reply
        assert "08:00 New York 🇺🇸" in reply
        assert "22:00 Tokyo 🇯🇵" in reply
        assert "|" in reply

    def test_day_offset(self):
        """Test day shift indicator (+1)."""
        # Berlin 23:00 -> Tokyo 07:00 next day
        members = [
            {"city": "Tokyo", "timezone": "Asia/Tokyo", "flag": "🇯🇵", "username": "charlie"}
        ]
        
        reply = format_conversion_reply(
            original_time="23:00",
            sender_city="Berlin",
            sender_tz="Europe/Berlin",
            sender_flag="🇩🇪",
            members=members
        )
        
        assert "07:00⁺¹ Tokyo 🇯🇵" in reply
