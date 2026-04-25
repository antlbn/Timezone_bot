from typing import Protocol
from core.domain.commands import Command, DeliveryResult
from core.domain.enums import Platform

class DeliveryPort(Protocol):
    async def deliver(self, platform: Platform, commands: list[Command]) -> DeliveryResult:
        """Routes user-facing delivery commands to the platform executor."""
        ...

    async def deliver_and_log(self, platform: Platform, commands: list[Command], *, user_id: int, chat_id: str) -> DeliveryResult:
        """Delivers commands and logs any failures with context."""
        ...
