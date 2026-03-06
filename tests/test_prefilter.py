import pytest
from src.capture import should_call_llm
from unittest.mock import patch

def test_prefilter_disabled_by_default():
    """If prefilter is disabled, it should always return True."""
    with patch("src.capture.get_prefilter_settings", return_value={"enabled": False}):
        assert should_call_llm("any random text") is True

def test_prefilter_strict_match():
    """Test strict time patterns."""
    settings = {
        "enabled": True,
        "strict_patterns": [r"\b([0-1]?[0-9]|2[0-3]):([0-5][0-9])\b"]
    }
    with patch("src.capture.get_prefilter_settings", return_value=settings):
        assert should_call_llm("Let's meet at 15:30") is True
        assert should_call_llm("Meeting is at 9:00") is True
        assert should_call_llm("No time here") is False

def test_prefilter_keyword_plus_numeric():
    """Test keywords + numeric candidate combination."""
    settings = {
        "enabled": True,
        "keywords": ["созвон", "meeting"],
        "numeric_candidate_pattern": r"\b([0-1]?[0-9]|2[0-3])\b",
        "strict_patterns": []
    }
    with patch("src.capture.get_prefilter_settings", return_value=settings):
        # Keyword + number
        assert should_call_llm("завтра созвон в 8") is True
        assert should_call_llm("Meeting at 19") is True
        
        # Keyword only (no number)
        assert should_call_llm("Lets have a meeting") is False
        
        # Number only (no keyword)
        assert should_call_llm("I have 8 apples") is False

def test_prefilter_case_insensitivity():
    """Ensure keywords are case-insensitive."""
    settings = {
        "enabled": True,
        "keywords": ["СОЗВОН"],
        "numeric_candidate_pattern": r"\b([0-1]?[0-9]|2[0-3])\b",
        "strict_patterns": []
    }
    with patch("src.capture.get_prefilter_settings", return_value=settings):
        assert should_call_llm("созвон в 10") is True
