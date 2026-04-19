from typing import Protocol
from core.domain.commands import Command

class CommandExecutorPort(Protocol):
    async def execute(self, commands: list[Command]) -> None:
        """Executes a list of commands natively on the target platform."""
        ...
