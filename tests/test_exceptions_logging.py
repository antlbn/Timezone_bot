import pytest
from unittest.mock import MagicMock, patch
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import logging

from src.geo import get_timezone_by_city
from src.formatter import normalize_time
from src.commands.middleware import PassiveCollectionMiddleware
from aiogram.types import Message, Chat, User

# ----------------------------------------------------------------------
# 1. Geo Tests: Verify API Failures are Handled & Logged
# ----------------------------------------------------------------------

def test_geo_timeout_logging(caplog):
    """Test that GeocoderTimedOut is caught and logged as warning."""
    with patch("src.geo._geolocator.geocode", side_effect=GeocoderTimedOut("Connection lost")):
        with caplog.at_level(logging.ERROR):
            result = get_timezone_by_city("Lost City")
            
            # Should return error dict
            assert isinstance(result, dict)
            assert "error" in result
            assert "Geocoding service unavailable" in result["error"]
            
            # Should capture error log
            assert "Geocoding error for 'Lost City'" in caplog.text
            assert "Connection lost" in caplog.text

def test_geo_service_error_logging(caplog):
    """Test that GeocoderServiceError (500/503) is caught and logged."""
    with patch("src.geo._geolocator.geocode", side_effect=GeocoderServiceError("Service unavailable")):
        with caplog.at_level(logging.ERROR):
            result = get_timezone_by_city("Berlin")
            assert isinstance(result, dict)
            assert "error" in result
            assert "Geocoding error for 'Berlin'" in caplog.text

# ----------------------------------------------------------------------
# 2. Formatter Tests: Parsing Robustness
# ----------------------------------------------------------------------

def test_normalize_time_debug_logging(caplog):
    """Test that invalid time strings log debug details but don't crash."""
    with caplog.at_level(logging.DEBUG):
        # Pass garbage input
        input_str = "Invalid Time String"
        result = normalize_time(input_str)
        
        # Should return original string (fallback behavior)
        assert result == input_str
        
        # Should log debug message for developer
        assert "Time normalization failed" in caplog.text
        assert input_str in caplog.text

# ----------------------------------------------------------------------
# 3. Middleware Tests: DB Failure Resilience
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_middleware_db_failure_logging(caplog):
    """Test that middleware doesn't crash bot if DB fails."""
    # Mock storage to raise exception
    with patch("src.storage.storage.get_user", side_effect=Exception("Database connection missing")):
        middleware = PassiveCollectionMiddleware()
        
        # Dummy handler that just returns "OK"
        async def dummy_handler(event, data):
            return "OK"
            
        # Create dummy message
        event = MagicMock(spec=Message)
        event.chat = Chat(id=-100, type="group")
        event.from_user = User(id=123, is_bot=False, first_name="Test")
        
        with caplog.at_level(logging.WARNING):
            # Should NOT raise Exception
            result = await middleware(dummy_handler, event, {})
            
            # Handler should still execute!
            assert result == "OK"
            
            # Error should be logged
            assert "Middleware storage error" in caplog.text
            assert "Database connection missing" in caplog.text
