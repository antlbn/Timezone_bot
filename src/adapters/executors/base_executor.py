from abc import ABC, abstractmethod
from core.domain.commands import (
    Command,
    CommandResult,
    SendReply,
    ShowOnboarding,
)
from ports.executor import CommandExecutorPort
import logging

logger = logging.getLogger(__name__)

class BaseCommandExecutor(CommandExecutorPort, ABC):
    def __init__(self):
        self._handlers = {
            SendReply: self._handle_send_reply,
            ShowOnboarding: self._handle_show_onboarding,
        }

    async def execute(self, commands: list[Command]) -> list[CommandResult]:
        results: list[CommandResult] = []
        for cmd in commands:
            handler = self._handlers.get(type(cmd))
            if not handler:
                logger.warning("Unknown command type: %s", type(cmd))
                results.append(
                    CommandResult(
                        command_name=type(cmd).__name__,
                        ok=False,
                        error="unknown_command",
                    )
                )
                continue

            try:
                await handler(cmd)
                results.append(CommandResult(command_name=type(cmd).__name__, ok=True))
            except Exception as exc:
                logger.exception("Command %s failed: %s", type(cmd).__name__, exc)
                results.append(
                    CommandResult(
                        command_name=type(cmd).__name__,
                        ok=False,
                        error=str(exc),
                    )
                )
        return results

    @abstractmethod
    async def _handle_send_reply(self, cmd: SendReply) -> None:
        pass

    @abstractmethod
    async def _handle_show_onboarding(self, cmd: ShowOnboarding) -> None:
        pass
