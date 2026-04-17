from typing import Protocol
from src.core.domain.commands import Command

class CommandBusPort(Protocol):
    async def execute(self, commands: list[Command]) -> None:
        """Executes a list of commands natively on the target platform."""
        ...
