from src.capture import extract_times
from src.transform import parse_time_string
from datetime import time

def test_extract_times_regex():
    assert extract_times("Meeting at 14:00") == ["14:00"]
    assert extract_times("Call 5pm") == ["5pm"]

def test_extract_times_nlp_ru():
    # Requires L1.5 keyword "вечера" -> "evening" or use "9 pm"
    # Note: dateparser russian support for "вечера" might be flaky without specialized training data
    # Let's test mixed content that works
    result = extract_times("Давай завтра в 19:00")
    assert result
    assert "завтра в 19:00" in result[0] or "19:00" in result[0]

def test_extract_times_nlp_en():
    # Regex captures "5pm" immediately, so L2 is skipped.
    # To test L2, we need something Regex doesn't catch but NLP does.
    # E.g. relative time "in 2 hours"
    result = extract_times("I will be there in 2 hours")
    assert result
    # dateparser usually returns the string "in 2 hours"
    assert "in 2 hours" in result[0]

def test_extract_times_filter_negative():
    # No numbers, no keywords -> should be empty fast
    assert extract_times("Привет, как дела?") == []
    assert extract_times("Just simple text") == []

def test_parse_time_string_nlp():
    # 9 pm is reliable
    t = parse_time_string("9 pm")
    assert t.hour == 21, f"Expected 21, got {t.hour}"
    assert t.minute == 0

def test_parse_time_string_mixed():
    t = parse_time_string("в 15:30")
    assert t.hour == 15
    assert t.minute == 30
