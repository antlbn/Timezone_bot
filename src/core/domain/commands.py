from dataclasses import dataclass

@dataclass(frozen=True)
class Command:
    """Base delivery command."""
    pass


@dataclass(frozen=True)
class CommandResult:
    command_name: str
    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class DeliveryResult:
    results: list[CommandResult]

@dataclass(frozen=True)
class SendReply(Command):
    text: str
    chat_id: str
    thread_id: str | None = None

@dataclass(frozen=True)
class ShowOnboarding(Command):
    user_id: int
    author_name: str
    chat_id: str
    thread_id: str | None = None
