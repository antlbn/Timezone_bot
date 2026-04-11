from src.core.services.conversion import convert_time, parse_time
from datetime import time

def test_conversion_convert_time():
    t, shift = convert_time("15:00", "Europe/Berlin", "Europe/Helsinki")
    # Berlin is UTC+1 (or +2 DST), Helsinki is UTC+2 (or +3 DST). Difference is 1 hour exactly both in standard and DST (most of the year, usually).
    # Since we use current date, it might be 16:00.
    # We will test without reference_date and just check it works generally. Let's provide a reference date to be sure.
    from datetime import datetime, timezone
    ref = datetime(2023, 1, 1, tzinfo=timezone.utc)
    t, shift = convert_time("15:00", "Europe/Berlin", "Europe/Helsinki", reference_date=ref)
    assert t == "16:00"
    assert shift == 0

def test_conversion_parse_time():
    assert parse_time("15:00") == time(15, 0)
    assert parse_time("3:00 PM") == time(15, 0)
    assert parse_time("3 PM") == time(15, 0)
    assert parse_time("12:00 AM") == time(0, 0)
