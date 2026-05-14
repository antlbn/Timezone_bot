from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from core.domain.value_objects import TimePoint
from ports.detection import DetectionResult


class DetectionPointPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    tz_city: str | None
    event_title: str | None
    am_pm_clear: bool

    def to_time_point(self) -> TimePoint:
        return TimePoint(
            time=self.time,
            tz_city=self.tz_city,
            am_pm_clear=self.am_pm_clear,
            event_title=self.event_title,
        )


class DetectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_mentioned: bool
    points: list[DetectionPointPayload]

    def to_detection_result(self) -> DetectionResult:
        return DetectionResult(
            time_mentioned=self.time_mentioned,
            points=tuple(point.to_time_point() for point in self.points),
        )
