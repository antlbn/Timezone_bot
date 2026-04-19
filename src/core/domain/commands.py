from dataclasses import dataclass

from core.domain.enums import Platform
from core.domain.value_objects import OnboardingPendingMessage

@dataclass(frozen=True)
class Command:
    """Base Command class."""
    pass

@dataclass(frozen=True)
class SendReply(Command):
    text: str
    chat_id: str
    thread_id: str | None = None

@dataclass(frozen=True)
class SaveOnboardingPending(Command):
    user_id: int
    platform: Platform
    message: OnboardingPendingMessage

@dataclass(frozen=True)
class ShowOnboarding(Command):
    user_id: int
    author_name: str
    chat_id: str
    thread_id: str | None = None

@dataclass(frozen=True)
class MarkOnboardingPromptShown(Command):
    user_id: int
    platform: Platform

@dataclass(frozen=True)
class NoOp(Command):
    pass
