import pytest
from dataclasses import FrozenInstanceError
from core.domain.value_objects import TimePoint
from core.domain.enums import Platform

def test_timepoint_validation_valid():
    """Test valid time format -> OK."""
    tp = TimePoint("15:00")
    assert tp.time == "15:00"

def test_timepoint_validation_invalid():
    """Test invalid time format -> ValueError."""
    with pytest.raises(ValueError):
        TimePoint("25:00")
    
    with pytest.raises(ValueError):
        TimePoint("15:60")

def test_timepoint_is_frozen():
    """Test that value objects cannot be mutated."""
    tp = TimePoint("15:00")
    with pytest.raises(FrozenInstanceError):
        tp.time = "16:00"  # type: ignore
