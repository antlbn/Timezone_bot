from abc import ABC, abstractmethod
from typing import Any
from src.core.domain.commands import Command, SavePending, NoOp, SendReply, ShowOnboarding
from src.ports.pending import PendingPort
import logging

logger = logging.getLogger(__name__)

class BaseCommandExecutor(ABC):
    def __init__(self, pending_port: PendingPort):
        self.pending_port = pending_port

    async def execute(self, commands: list[Command]) -> None:
        for cmd in commands:
            if isinstance(cmd, SavePending):
                await self._handle_save_pending(cmd)
            elif isinstance(cmd, NoOp):
                self._handle_noop()
            elif isinstance(cmd, SendReply):
                await self._handle_send_reply(cmd)
            elif isinstance(cmd, ShowOnboarding):
                await self._handle_show_onboarding(cmd)
            else:
                logger.warning(f"Unknown command type: {type(cmd)}")

    async def _handle_save_pending(self, cmd: SavePending) -> None:
        await self.pending_port.save(cmd.user_id, cmd.platform, cmd.message)

    def _handle_noop(self) -> None:
        pass

    @abstractmethod
    async def _handle_send_reply(self, cmd: SendReply) -> None:
        pass

    @abstractmethod
    async def _handle_show_onboarding(self, cmd: ShowOnboarding) -> None:
        pass
