from core.domain.enums import Platform
from core.domain.value_objects import UserProfile
from ports.repositories import UserRepositoryPort, ChatRepositoryPort
from core.services.conversion import get_utc_offset

from ports.time import TimePort

class ProfileService:
    def __init__(
        self,
        users_repo: UserRepositoryPort,
        chats_repo: ChatRepositoryPort,
        time_port: TimePort,
    ) -> None:
        self._users = users_repo
        self._chats = chats_repo
        self._time = time_port

    async def get_user(self, user_id: int, platform: Platform) -> UserProfile | None:
        return await self._users.get_user(user_id, platform)

    async def get_sorted_chat_members(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        members = await self._chats.get_chat_members(chat_id, platform)
        if not members:
            return []

        return sorted(members, key=self._member_sort_key)

    def _member_sort_key(self, member: UserProfile) -> tuple[int, float, str]:
        """Sort configured members by UTC offset and keep unconfigured users at the end."""
        if not member.timezone:
            return (1, 0.0, member.city or member.username or "")

        now = self._time.now_utc()
        return (0, get_utc_offset(member.timezone, now=now), member.city or member.username or "")
    async def remove_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        """Remove a user from a specific chat's list."""
        await self._chats.remove_chat_member(chat_id, user_id, platform)
