from dataclasses import dataclass

from core.domain.enums import Platform
from core.domain.value_objects import PendingMessage

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
class SavePending(Command):
    user_id: int
    platform: Platform
    message: PendingMessage

@dataclass(frozen=True)
class ShowOnboarding(Command):
    user_id: int
    author_name: str
    chat_id: str
    thread_id: str | None = None

@dataclass(frozen=True)
class NoOp(Command):
    pass
