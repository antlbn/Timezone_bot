from core.domain.enums import Platform
from core.domain.value_objects import UserProfile
from ports.repositories import UserRepositoryPort, ChatRepositoryPort
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime
from core.services.conversion import get_utc_offset

class ProfileService:
    def __init__(self, users_repo: UserRepositoryPort, chats_repo: ChatRepositoryPort) -> None:
        self._users = users_repo
        self._chats = chats_repo

    async def get_user(self, user_id: int, platform: Platform) -> UserProfile | None:
        return await self._users.get_user(user_id, platform)

    async def get_sorted_chat_members(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        members = await self._chats.get_chat_members(chat_id, platform)
        if not members:
            return []

        # sort by timezone offset
        return sorted(members, key=lambda m: get_utc_offset(m.timezone))
