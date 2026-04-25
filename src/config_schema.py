from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class LoggingSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str = "INFO"


class BotSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    show_usernames: bool = False
    show_event_title: bool = True
    response_style: Literal["block", "inline_sentence"] = "block"
    max_age_fresh_secs: int = 30
    onboarding_cooldown_secs: int = 3600
    onboarding_pending_ttl_secs: int = 3600
    group_auto_delete_delay_secs: int = 20


class EventDetectionSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    log_prompts: bool = False
    max_message_hard_skip_chars: int = 4000


class YamlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logging: LoggingSection = LoggingSection()
    bot: BotSection = BotSection()
    event_detection: EventDetectionSection = EventDetectionSection()
