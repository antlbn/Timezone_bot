from dataclasses import dataclass
from typing import Protocol
from datetime import datetime

from core.domain.value_objects import TimePoint

@dataclass
class DetectionRequest:
    text: str
    timestamp: datetime

@dataclass
class DetectionResult:
    time_mentioned: bool
    points: tuple[TimePoint, ...]

class DetectionPort(Protocol):
    async def detect(self, request: DetectionRequest) -> DetectionResult:
        ...
