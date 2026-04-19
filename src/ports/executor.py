from typing import Protocol
from core.domain.commands import Command

class CommandExecutorPort(Protocol):
    async def execute(self, commands: list[Command]) -> None:
        """Executes user-facing delivery commands on the target platform."""
        ...
