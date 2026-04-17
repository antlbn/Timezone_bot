from abc import ABC, abstractmethod
from src.core.domain.commands import Command, SavePending, NoOp, SendReply, ShowOnboarding
from src.ports.pending import PendingPort
from src.ports.executor import CommandExecutorPort
import logging

logger = logging.getLogger(__name__)

class BaseCommandExecutor(CommandExecutorPort, ABC):
    def __init__(self, pending_port: PendingPort):
        self.pending_port = pending_port
        self._handlers = {
            SavePending: self._handle_save_pending,
            NoOp: self._handle_noop,
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

    async def _handle_save_pending(self, cmd: SavePending) -> None:
        await self.pending_port.save(cmd.user_id, cmd.platform, cmd.message)

    async def _handle_noop(self, cmd: NoOp) -> None:
        pass

    @abstractmethod
    async def _handle_send_reply(self, cmd: SendReply) -> None:
        pass

    @abstractmethod
    async def _handle_show_onboarding(self, cmd: ShowOnboarding) -> None:
        pass
