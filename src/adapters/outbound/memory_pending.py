from time import monotonic
from core.domain.enums import Platform
from core.domain.value_objects import PendingMessage
from ports.pending import PendingPort

class MemoryPending(PendingPort):
    """In-memory pending store with TTL.
    The TTL doubles as the onboarding cooldown:
    if a pending message exists (not yet expired), the user is within the cooldown window
    and OnboardingGateStage will stop the pipeline (no re-prompt).
    When the TTL expires, has_pending() returns False and the gate lets through again.
    """
    def __init__(self, ttl_seconds: int = 3600):
        # (user_id, platform_value) → list of (expires_at, message)
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

    async def has_pending(self, user_id: int, platform: Platform) -> bool:
        """True if user has at least one non-expired pending message.
        Used by OnboardingGateStage to detect cooldown window.
        """
        self._cleanup()
        return (user_id, platform.value) in self._store
