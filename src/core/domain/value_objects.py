from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TYPE_CHECKING

from core.domain.enums import Platform, ResponseStyle

if TYPE_CHECKING:
    from ports.detection import DetectionResult
    from core.domain.commands import Command

@dataclass(frozen=True)
class TimePoint:
    time: str
    tz_city: str | None = None
    tz_resolved: str | None = None   # IANA timezone resolved from tz_city by GeoResolveStage
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
    username: str | None = None
    city: str | None = None
    timezone: str | None = None
    flag: str | None = None
    onboarding_declined: bool = False

@dataclass(frozen=True)
class OnboardingPendingMessage:
    original_input: InputData
    detection: DetectionResult  # Checkpoint: detection was done, geo was resolved; store here to skip re-detection on replay

@dataclass(frozen=True)
class InputData:
    text: str
    user_id: int
    platform: Platform
    author_name: str
    timestamp_utc: datetime
    chat_id: str
    thread_id: str | None = None
    is_bot: bool = False

@dataclass(frozen=True)
class BotSettings:
    show_usernames: bool = False
    show_event_title: bool = True
    response_style: ResponseStyle = ResponseStyle.BLOCK
    max_age_fresh_secs: int = 30
    onboarding_cooldown_secs: int = 3600  # How long to wait before re-prompting an ignoring user
    onboarding_pending_ttl_secs: int = 3600

@dataclass
class MessageContext:
    input: InputData
    detection: DetectionResult | None = None  # Set by DetectionStage (fresh) or pre-loaded from OnboardingPendingMessage (replay)
    sender: UserProfile | None = None
    reply_text: str | None = None
    commands: list[Command] = field(default_factory=list)
    members: list[UserProfile] = field(default_factory=list)
    onboarding_prompt_suppressed: bool = False
    _stopped: bool = False
