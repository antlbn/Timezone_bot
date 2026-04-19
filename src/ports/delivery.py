from typing import Protocol
from core.domain.commands import Command
from core.domain.enums import Platform

class DeliveryPort(Protocol):
    async def deliver(self, platform: Platform, commands: list[Command]) -> None:
        """Routes user-facing delivery commands to the platform executor."""
        ...
