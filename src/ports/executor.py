from typing import Protocol
from core.domain.commands import Command, CommandResult

class CommandExecutorPort(Protocol):
    async def execute(self, commands: list[Command]) -> list[CommandResult]:
        """Executes user-facing delivery commands on the target platform."""
        ...
