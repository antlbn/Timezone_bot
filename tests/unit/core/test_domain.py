import pytest
from dataclasses import FrozenInstanceError
from core.domain.value_objects import TimePoint


def test_timepoint_validation_valid():
    """Test valid time format -> OK."""
    tp = TimePoint(time="15:30")
    assert tp.time == "15:30"


def test_timepoint_validation_invalid():
    """Bad time format -> ValueError."""
    with pytest.raises(ValueError):
        TimePoint(time="25:99")
    with pytest.raises(ValueError):
        TimePoint(time="hello")


def test_timepoint_is_frozen():
    """TimePoint is immutable."""
    tp = TimePoint(time="10:00")
    with pytest.raises(FrozenInstanceError):
        tp.time = "11:00"
