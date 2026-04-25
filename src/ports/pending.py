from typing import Protocol
from core.domain.value_objects import OnboardingPendingMessage
from core.domain.enums import Platform

class OnboardingPendingPort(Protocol):
    async def upsert(
        self,
        user_id: int,
        platform: Platform,
        chat_id: str,
        message: OnboardingPendingMessage,
    ) -> None:
        ...

    async def get(
        self,
        user_id: int,
        platform: Platform,
        chat_id: str,
    ) -> OnboardingPendingMessage | None:
        ...

    async def list_for_user(
        self,
        user_id: int,
        platform: Platform,
    ) -> list[OnboardingPendingMessage]:
        ...

    async def delete(
        self,
        user_id: int,
        platform: Platform,
        chat_id: str,
    ) -> None:
        ...
