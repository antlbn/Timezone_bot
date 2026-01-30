"""Tests for time transformation module."""
import pytest
from datetime import time
from src.transform import parse_time_string, convert_time, get_utc_offset


class TestParseTimeString:
    """Test parse_time_string function."""
    
    # ============================================================
    # 24h format
    # ============================================================
    
    def test_24h_standard(self):
        """Standard 24h time."""
        t = parse_time_string("14:00")
        assert t.hour == 14
        assert t.minute == 0
    
    def test_24h_with_minutes(self):
        """24h with minutes."""
        t = parse_time_string("9:30")
        assert t.hour == 9
        assert t.minute == 30
    
    def test_24h_midnight(self):
        """Midnight."""
        t = parse_time_string("00:00")
        assert t.hour == 0
        assert t.minute == 0
    
    # ============================================================
    # 12h format
    # ============================================================
    
    def test_12h_pm(self):
        """5 PM = 17:00."""
        t = parse_time_string("5 pm")
        assert t.hour == 17
        assert t.minute == 0
    
    def test_12h_am(self):
        """9 AM = 09:00."""
        t = parse_time_string("9 AM")
        assert t.hour == 9
        assert t.minute == 0
    
    def test_12h_noon(self):
        """12 PM = 12:00 (noon)."""
        t = parse_time_string("12 pm")
        assert t.hour == 12
        assert t.minute == 0
    
    def test_12h_midnight_am(self):
        """12 AM = 00:00 (midnight)."""
        t = parse_time_string("12 AM")
        assert t.hour == 0
        assert t.minute == 0
    
    def test_12h_with_minutes(self):
        """5:30 PM."""
        t = parse_time_string("5:30 PM")
        assert t.hour == 17
        assert t.minute == 30


class TestConvertTime:
    """Test convert_time function."""
    
    def test_same_timezone(self):
        """Same timezone should return same time."""
        result, offset = convert_time("14:00", "Europe/Berlin", "Europe/Berlin")
        assert result == "14:00"
        assert offset == 0
    
    def test_berlin_to_new_york(self):
        """Berlin to New York (usually -6 hours)."""
        result, offset = convert_time("14:00", "Europe/Berlin", "America/New_York")
        # Note: exact offset depends on DST, but should be earlier
        assert result < "14:00" or offset == -1
    
    def test_utc_to_tokyo(self):
        """UTC to Tokyo (+9 hours)."""
        result, offset = convert_time("15:00", "UTC", "Asia/Tokyo")
        # 15:00 UTC = 00:00 next day Tokyo
        assert result == "00:00" or result == "24:00" or offset == 1
    
    def test_day_offset_next_day(self):
        """Time that crosses to next day."""
        result, offset = convert_time("23:00", "Europe/London", "Asia/Tokyo")
        # 23:00 London + 9h = 08:00 next day Tokyo
        assert offset == 1
    
    def test_day_offset_previous_day(self):
        """Time that goes to previous day."""
        result, offset = convert_time("01:00", "Asia/Tokyo", "America/Los_Angeles")
        # 01:00 Tokyo - 17h = some time previous day LA
        assert offset == -1


class TestGetUtcOffset:
    """Test get_utc_offset function."""
    
    def test_utc_is_zero(self):
        """UTC offset should be 0."""
        offset = get_utc_offset("UTC")
        assert offset == 0
    
    def test_tokyo_positive(self):
        """Tokyo should be positive offset."""
        offset = get_utc_offset("Asia/Tokyo")
        assert offset > 0
    
    def test_new_york_negative(self):
        """New York should be negative offset."""
        offset = get_utc_offset("America/New_York")
        assert offset < 0
