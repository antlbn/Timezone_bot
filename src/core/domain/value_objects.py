from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from core.domain.enums import Platform, ResponseStyle

if TYPE_CHECKING:
    from ports.detection import DetectionResult

@dataclass(frozen=True)
class LLMModelConfig:
    api_key: str
    model: str
    base_url: str | None = None

@dataclass(frozen=True)
class LLMConfig:
    primary: LLMModelConfig
    fallback: LLMModelConfig | None = None

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

    @property
    def needs_onboarding(self) -> bool:
        return not self.timezone and not self.onboarding_declined

@dataclass(frozen=True)
class OnboardingPendingMessage:
    original_input: InputData
    detection: DetectionResult  # Checkpoint: detection was done, geo was resolved; store here to skip re-detection on replay

@dataclass(frozen=True)
class MessageDecision:
    reply_text: str | None = None
    pending_message: OnboardingPendingMessage | None = None
    needs_onboarding: bool = False
    ignore: bool = False

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

@dataclass(frozen=True)
class MessageContext:
    input: InputData
    detection: DetectionResult | None = None  # Set by DetectionStage (fresh) or pre-loaded from OnboardingPendingMessage (replay)
    sender: UserProfile | None = None
    reply_text: str | None = None
    members: tuple[UserProfile, ...] = field(default_factory=tuple)
    decision: MessageDecision | None = None
    stop_processing: bool = False
