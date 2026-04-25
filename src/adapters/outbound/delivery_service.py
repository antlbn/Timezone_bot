import logging

from core.domain.commands import Command, CommandResult, DeliveryResult
from core.domain.enums import Platform
from ports.executor import CommandExecutorPort
from ports.delivery import DeliveryPort

logger = logging.getLogger(__name__)


class DeliveryService(DeliveryPort):
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

    def register_executor(self, platform: Platform, executor: CommandExecutorPort) -> None:
        self._routes[platform] = executor

    async def deliver(self, platform: Platform, commands: list[Command]) -> DeliveryResult:
        if not commands:
            return DeliveryResult(results=[])
        executor = self._routes.get(platform)
        if executor is None:
            logger.warning("No executor configured for platform %s", platform)
            return DeliveryResult(
                results=[
                    CommandResult(
                        command_name=type(command).__name__,
                        ok=False,
                        error="missing_executor",
                    )
                    for command in commands
                ]
            )
        return DeliveryResult(results=await executor.execute(commands))

    async def deliver_and_log(self, platform: Platform, commands: list[Command], *, user_id: int, chat_id: str) -> DeliveryResult:
        result = await self.deliver(platform, commands)
        for r in result.results:
            if not r.ok:
                logger.warning(
                    "Delivery failed user=%s chat=%s platform=%s command=%s error=%s",
                    user_id, chat_id, platform.value, r.command_name, r.error,
                )
        return result
