from src.core.domain.enums import Platform
from src.core.domain.value_objects import UserProfile, PendingMessage, TimePoint
from src.ports.storage import StoragePort
from src.ports.detection import DetectionPort, DetectionRequest, DetectionResult
from src.ports.geocoding import GeoPort, Location
from src.ports.pending import PendingPort
from src.ports.executor import CommandExecutorPort
from src.core.domain.commands import Command

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

class FakeGeoPort(GeoPort):
    def __init__(self, resolves_to: Location | None = None):
        self._resolves_to = resolves_to

    async def resolve_city(self, name: str) -> Location | None:
        return self._resolves_to

class FakePendingPort(PendingPort):
    def __init__(self):
        self.messages = {}

    async def save_pending(self, user_id: int, platform: Platform, message: PendingMessage) -> None:
        key = (user_id, platform)
        if key not in self.messages:
            self.messages[key] = []
        self.messages[key].append(message)

    async def get_and_clear_pending(self, user_id: int, platform: Platform) -> list[PendingMessage]:
        key = (user_id, platform)
        msgs = self.messages.get(key, [])
        self.messages[key] = []
        return msgs

class FakeCommandExecutorPort(CommandExecutorPort):
    def __init__(self):
        self.executed_commands = []

    async def execute(self, commands: list[Command]) -> None:
        self.executed_commands.extend(commands)
