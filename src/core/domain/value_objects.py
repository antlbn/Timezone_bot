from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TYPE_CHECKING

from src.core.domain.enums import Platform, ResponseStyle

if TYPE_CHECKING:
    from src.ports.detection import DetectionResult
    from src.core.domain.commands import Command

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
    is_bot: bool = False

@dataclass(frozen=True)
class BotSettings:
    show_usernames: bool = False
    show_event_title: bool = True
    response_style: ResponseStyle = ResponseStyle.BLOCK

@dataclass
class MessageContext:
    input: InputData
    detection: DetectionResult | None = None
    sender: UserProfile | None = None
    reply_text: str | None = None
    commands: list[Command] = field(default_factory=list)
    members: list[UserProfile] = field(default_factory=list)
    _stopped: bool = False
