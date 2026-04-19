from datetime import time, datetime, timezone
import pytest

from core.services.conversion import convert_time, parse_time


def test_conversion_convert_time():
    ref = datetime(2023, 1, 1, tzinfo=timezone.utc)
    t, shift = convert_time("15:00", "Europe/Berlin", "Europe/Helsinki", reference_date=ref)
    assert t == "16:00"
    assert shift == 0


def test_conversion_parse_time():
    assert parse_time("15:00") == time(15, 0)
    assert parse_time("3:00 PM") == time(15, 0)
    assert parse_time("3 PM") == time(15, 0)
    assert parse_time("12:00 AM") == time(0, 0)


def test_conversion_parse_time_invalid_returns_none():
    assert parse_time("not-a-time") is None


def test_conversion_convert_time_returns_day_shift():
    ref = datetime(2023, 1, 1, tzinfo=timezone.utc)
    t, shift = convert_time("23:30", "Europe/Berlin", "Asia/Tokyo", reference_date=ref)
    assert t == "07:30"
    assert shift == 1


def test_conversion_convert_time_invalid_raises_value_error():
    with pytest.raises(ValueError):
        convert_time("bad", "Europe/Berlin", "Asia/Tokyo")
