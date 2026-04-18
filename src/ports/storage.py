from typing import Protocol
from src.core.domain.value_objects import UserProfile
from src.core.domain.enums import Platform

class StoragePort(Protocol):
    async def get_user(self, user_id: int, platform: Platform) -> UserProfile | None:
        ...

    async def set_user(self, user_id: int, platform: Platform, timezone: str, city: str | None = None, flag: str | None = None, username: str | None = None) -> None:
        ...

    async def set_onboarding_declined(self, user_id: int, platform: Platform, username: str | None = None) -> None:
        ...

    async def get_chat_members(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        ...

    async def add_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        ...

    async def remove_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        ...

    async def update_activity(self, chat_id: str, user_id: int, platform: Platform) -> None:
        ...



