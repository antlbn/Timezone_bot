from typing import Protocol
from src.core.domain.value_objects import PendingMessage
from src.core.domain.enums import Platform

class PendingPort(Protocol):
    async def save(self, user_id: int, platform: Platform, message: PendingMessage) -> None:
        ...

    async def get_and_delete(self, user_id: int, platform: Platform) -> list[PendingMessage]:
        ...
