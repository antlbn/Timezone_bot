"""Tests for geo module - city lookup and timezone resolution."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import time


class TestGetTimezoneByCity:
    """Tests for get_timezone_by_city function."""
    
    def test_valid_city_returns_timezone(self):
        """Test that a known city returns correct timezone info."""
        from src.geo import get_timezone_by_city
        
        # Use a well-known city that geocoding should always find
        result = get_timezone_by_city("Berlin")
        
        assert result is not None
        assert "error" not in result
        assert result["timezone"] == "Europe/Berlin"
        assert result["city"] == "Berlin"
        assert result["flag"] != ""  # Should have a flag

    def test_invalid_city_returns_none(self):
        """Test that nonexistent city returns None."""
        from src.geo import get_timezone_by_city
        
        result = get_timezone_by_city("Nonexistent_City_12345xyz")
        
        assert result is None

    def test_geocoder_timeout_returns_error_dict(self):
        """Test that geocoder timeout returns error dict, not exception."""
        from src.geo import get_timezone_by_city
        from geopy.exc import GeocoderTimedOut
        
        with patch("src.geo._geolocator.geocode", side_effect=GeocoderTimedOut("Timeout")):
            result = get_timezone_by_city("Berlin")
            
            assert result is not None
            assert "error" in result


class TestGetTimezoneByOffset:
    """Tests for get_timezone_by_offset function."""
    
    def test_positive_offset(self):
        """Test UTC+3 offset."""
        from src.geo import get_timezone_by_offset
        
        result = get_timezone_by_offset(3.0)
        
        assert result["timezone"] == "Europe/Moscow"
        assert result["city"] == "UTC+3"
        assert result["flag"] == "🌐"
    
    def test_negative_offset(self):
        """Test UTC-5 offset (New York)."""
        from src.geo import get_timezone_by_offset
        
        result = get_timezone_by_offset(-5.0)
        
        assert result["timezone"] == "America/New_York"
        assert result["city"] == "UTC-5"
    
    def test_zero_offset(self):
        """Test UTC+0."""
        from src.geo import get_timezone_by_offset
        
        result = get_timezone_by_offset(0)
        
        assert result["timezone"] == "Europe/London"
        assert result["city"] == "UTC+0"
    
    def test_offset_clamped_to_range(self):
        """Test that extreme offsets are clamped to ±12."""
        from src.geo import get_timezone_by_offset
        
        result = get_timezone_by_offset(15)  # Beyond +12
        assert result["offset"] == 12
        
        result = get_timezone_by_offset(-15)  # Beyond -12
        assert result["offset"] == -12


class TestResolveTimezoneFromInput:
    """Tests for resolve_timezone_from_input - the universal resolver."""
    
    def test_time_input_returns_offset_timezone(self):
        """Test that time string like '15:30' resolves to offset-based timezone."""
        from src.geo import resolve_timezone_from_input
        
        # We can't predict exact offset without knowing current UTC,
        # but we CAN verify it returns a valid result with offset pattern
        result = resolve_timezone_from_input("15:30")
        
        assert result is not None
        assert "timezone" in result
        assert result["flag"] == "🌐"  # Offset-based timezones use globe
    
    def test_city_input_returns_city_timezone(self):
        """Test that city name resolves to geocoded timezone."""
        from src.geo import resolve_timezone_from_input
        
        result = resolve_timezone_from_input("Berlin")
        
        assert result is not None
        assert result["timezone"] == "Europe/Berlin"
        assert result["flag"] != "🌐"  # City should have country flag
    
    def test_invalid_input_returns_none(self):
        """Test that garbage input returns None."""
        from src.geo import resolve_timezone_from_input
        
        result = resolve_timezone_from_input("xyz123notacity")
        
        assert result is None
    
    def test_time_takes_priority_over_city(self):
        """Test that time pattern is checked BEFORE city geocoding.
        
        This prevents false matches like '19:53' -> Jakarta.
        """
        from src.geo import resolve_timezone_from_input
        
        # '10:00' should be treated as time, not geocoded
        result = resolve_timezone_from_input("10:00")
        
        assert result is not None
        assert result["flag"] == "🌐"  # Should be offset-based, not a city


class TestGetCountryFlag:
    """Tests for country code to emoji flag conversion."""
    
    def test_valid_country_code(self):
        """Test that valid country codes convert to flags."""
        from src.geo import get_country_flag
        
        assert get_country_flag("DE") == "🇩🇪"
        assert get_country_flag("US") == "🇺🇸"
        assert get_country_flag("JP") == "🇯🇵"
    
    def test_lowercase_country_code(self):
        """Test that lowercase codes work."""
        from src.geo import get_country_flag
        
        assert get_country_flag("de") == "🇩🇪"
    
    def test_invalid_country_code_returns_empty(self):
        """Test that invalid codes return empty string."""
        from src.geo import get_country_flag
        
        assert get_country_flag("") == ""
        assert get_country_flag("X") == ""
        assert get_country_flag("TOOLONG") == ""
        assert get_country_flag(None) == ""
