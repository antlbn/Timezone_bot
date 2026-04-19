import logging

from core.domain.commands import Command
from core.domain.enums import Platform
from ports.executor import CommandExecutorPort

logger = logging.getLogger(__name__)


class DeliveryService:
    """Routes user-facing delivery commands to the platform executor."""

    def __init__(
        self,
        tg_executor: CommandExecutorPort | None = None,
        dc_executor: CommandExecutorPort | None = None,
    ) -> None:
        self._routes: dict[Platform, CommandExecutorPort] = {}
        if tg_executor:
            self._routes[Platform.TELEGRAM] = tg_executor
        if dc_executor:
            self._routes[Platform.DISCORD] = dc_executor

    async def deliver(self, platform: Platform, commands: list[Command]) -> None:
        if not commands:
            return
        executor = self._routes.get(platform)
        if executor is None:
            logger.warning("No executor configured for platform %s", platform)
            return
        await executor.execute(commands)
