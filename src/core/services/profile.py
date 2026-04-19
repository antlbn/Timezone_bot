from core.domain.enums import Platform
from core.domain.value_objects import UserProfile
from ports.storage import StoragePort
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime

class ProfileService:
    def __init__(self, storage_port: StoragePort) -> None:
        self._storage = storage_port

    async def get_user(self, user_id: int, platform: Platform) -> UserProfile | None:
        return await self._storage.get_user(user_id, platform)

    async def get_sorted_chat_members(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        members = await self._storage.get_chat_members(chat_id, platform)
        if not members:
            return []

        def get_offset(tz_name: str) -> float:
            try:
                # get UTC offset in seconds
                return datetime.now(ZoneInfo(tz_name)).utcoffset().total_seconds()
            except (ValueError, ZoneInfoNotFoundError):
                return 0.0

        # sort by timezone offset
        return sorted(members, key=lambda m: get_offset(m.timezone))
