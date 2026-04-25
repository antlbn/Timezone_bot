import pytest
from pydantic import ValidationError

from adapters.outbound.detection_schema import DetectionPayload


def test_detection_payload_parses_valid_schema():
    payload = DetectionPayload.model_validate(
        {
            "time_mentioned": True,
            "points": [
                {
                    "time": "15:00",
                    "tz_city": "Berlin",
                    "event_title": "Call",
                    "am_pm_clear": True,
                }
            ],
        }
    )

    result = payload.to_detection_result()

    assert result.time_mentioned is True
    assert len(result.points) == 1
    assert result.points[0].time == "15:00"
    assert result.points[0].tz_city == "Berlin"


def test_detection_payload_rejects_legacy_or_unknown_fields():
    with pytest.raises(ValidationError):
        DetectionPayload.model_validate(
            {
                "time_mentioned": True,
                "event": "15:00",
                "points": [],
            }
        )
