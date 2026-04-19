from typing import Protocol
from core.domain.value_objects import OnboardingPendingMessage
from core.domain.enums import Platform

class OnboardingPendingPort(Protocol):
    async def upsert(self, user_id: int, platform: Platform, message: OnboardingPendingMessage) -> None:
        ...

    async def get(self, user_id: int, platform: Platform) -> OnboardingPendingMessage | None:
        ...

    async def delete(self, user_id: int, platform: Platform) -> None:
        ...

    async def get_and_delete(self, user_id: int, platform: Platform) -> OnboardingPendingMessage | None:
        ...
