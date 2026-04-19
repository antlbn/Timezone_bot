from typing import Protocol
from core.domain.value_objects import UserProfile
from core.domain.enums import Platform

class StoragePort(Protocol):
    async def get_user(self, user_id: int, platform: Platform) -> UserProfile | None:
        ...

    async def create_user(self, user_id: int, platform: Platform, author_name: str) -> UserProfile:
        """Insert a new user stub (first contact). Caller must check get_user first."""
        ...

    async def update_username(self, user_id: int, platform: Platform, author_name: str) -> None:
        """Update display name only. Called when name has changed since last message."""
        ...

    async def ensure_user_metadata(self, user_id: int, platform: Platform, username: str) -> None:
        """Efficiently create user or update username without a prior read."""
        ...

    async def set_user(self, user_id: int, platform: Platform, timezone: str, city: str | None = None, flag: str | None = None) -> None:
        """Set the user's timezone/city/flag after successful onboarding."""
        ...

    async def set_onboarding_declined(self, user_id: int, platform: Platform) -> None:
        """Mark that user explicitly opted out of onboarding."""
        ...

    async def get_chat_members(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        """Fetch all members linked to this chat."""
        ...

    async def get_chat_members_with_tz(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        """Fetch only members who have a timezone set."""
        ...

    async def add_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        ...

    async def remove_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        ...

    async def update_activity(self, chat_id: str, user_id: int, platform: Platform) -> None:
        ...
