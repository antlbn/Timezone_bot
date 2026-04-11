import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.core.domain.enums import Platform

@dataclass(frozen=True)
class TimePoint:
    time: str
    tz_city: str | None = None
    am_pm_clear: bool = True
    day_shift: int = 0
    event_title: str | None = None

    def __post_init__(self):
        # Validate time format HH:MM
        if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", self.time):
            raise ValueError(f"Invalid time format: {self.time}. Must be HH:MM.")

@dataclass(frozen=True)
class UserProfile:
    user_id: int
    platform: Platform
    city: str | None = None
    timezone: str | None = None
    flag: str | None = None
    onboarding_declined: bool = False

@dataclass(frozen=True)
class PendingMessage:
    text: str
    author_name: str
    chat_id: str
    timestamp_utc: datetime

@dataclass(frozen=True)
class InputData:
    text: str
    user_id: int
    platform: Platform
    author_name: str
    timestamp_utc: datetime
    chat_id: str
    sender: UserProfile | None = None
    is_bot: bool = False

@dataclass
class MessageContext:
    input: InputData
    detection: Any | None = None  # Will be DetectionResult
    reply_text: str | None = None
    commands: list[Any] = field(default_factory=list)  # Will be list[Command]
    _stopped: bool = False
