from time import monotonic
from src.core.domain.enums import Platform
from src.core.domain.value_objects import PendingMessage
from src.ports.pending import PendingPort

class MemoryPending(PendingPort):
    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[tuple[int, str], list[tuple[float, PendingMessage]]] = {}
        self.ttl = ttl_seconds

    def _cleanup(self):
        now = monotonic()
        for key in list(self._store.keys()):
            self._store[key] = [(expires, msg) for expires, msg in self._store[key] if expires > now]
            if not self._store[key]:
                del self._store[key]

    async def save(self, user_id: int, platform: Platform, message: PendingMessage) -> None:
        self._cleanup()
        expires = monotonic() + self.ttl
        self._store.setdefault((user_id, platform.value), []).append((expires, message))

    async def get_and_delete(self, user_id: int, platform: Platform) -> list[PendingMessage]:
        self._cleanup()
        items = self._store.pop((user_id, platform.value), [])
        return [msg for _, msg in items]
