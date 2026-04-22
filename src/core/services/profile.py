from core.domain.enums import Platform
from core.domain.value_objects import UserProfile
from ports.repositories import UserRepositoryPort, ChatRepositoryPort
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

        return sorted(members, key=self._member_sort_key)

    @staticmethod
    def _member_sort_key(member: UserProfile) -> tuple[int, float, str]:
        """Sort configured members by UTC offset and keep unconfigured users at the end."""
        if not member.timezone:
            return (1, 0.0, member.city or member.username or "")

        return (0, get_utc_offset(member.timezone), member.city or member.username or "")
    async def remove_timezone(self, user_id: int, platform: Platform, username: str = "") -> None:
        """Clear the user's timezone/city/flag."""
        await self._users.set_user(
            user_id=user_id,
            platform=platform,
            timezone=None,
            city=None,
            flag=None,
            username=username
        )

    async def remove_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        """Remove a user from a specific chat's list."""
        await self._chats.remove_chat_member(chat_id, user_id, platform)
