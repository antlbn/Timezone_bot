from abc import ABC, abstractmethod
from core.domain.commands import (
    Command,
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

    async def execute(self, commands: list[Command]) -> None:
        for cmd in commands:
            handler = self._handlers.get(type(cmd))
            if handler:
                await handler(cmd)
            else:
                logger.warning(f"Unknown command type: {type(cmd)}")

    @abstractmethod
    async def _handle_send_reply(self, cmd: SendReply) -> None:
        pass

    @abstractmethod
    async def _handle_show_onboarding(self, cmd: ShowOnboarding) -> None:
        pass
