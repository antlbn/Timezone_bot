from src.core.domain.enums import Platform
from src.core.domain.value_objects import UserProfile, PendingMessage, TimePoint
from src.ports.storage import StoragePort
from src.ports.detection import DetectionPort, DetectionRequest, DetectionResult

class FakeStoragePort:
    def __init__(self):
        self.users = {}
        self.members = {}

    async def get_user(self, user_id: int, platform: Platform) -> UserProfile | None:
        return self.users.get((user_id, platform))

    async def set_user(self, user_id: int, platform: Platform, timezone: str, city: str | None = None, flag: str | None = None) -> None:
        pass

    async def get_chat_members(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        return self.members.get((chat_id, platform), [])

    async def add_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        pass

    async def remove_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        pass

    async def update_activity(self, chat_id: str, user_id: int, platform: Platform) -> None:
        pass

class FakeDetectionPort:
    def __init__(self, time_mentioned: bool = True, points: list[TimePoint] = None):
        self._time_mentioned = time_mentioned
        self._points = points or []

    async def detect(self, request: DetectionRequest) -> DetectionResult:
        return DetectionResult(
            time_mentioned=self._time_mentioned,
            points=tuple(self._points)
        )
