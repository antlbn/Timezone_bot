from time import monotonic

from core.domain.enums import Platform
from core.domain.value_objects import OnboardingPendingMessage
from ports.pending import OnboardingPendingPort

class MemoryOnboardingPending(OnboardingPendingPort):
    """In-memory store for the latest onboarding-pending message per user."""
    def __init__(self, ttl_seconds: int = 3600, now_fn=None):
        # (user_id, platform_value) → (expires_at, message)
        self._store: dict[tuple[int, str], tuple[float, OnboardingPendingMessage]] = {}
        self.ttl = ttl_seconds
        self._now = now_fn or monotonic

    def _cleanup(self):
        now = self._now()
        for key in list(self._store.keys()):
            expires, _ = self._store[key]
            if expires <= now:
                del self._store[key]

    async def upsert(self, user_id: int, platform: Platform, message: OnboardingPendingMessage) -> None:
        self._cleanup()
        expires = self._now() + self.ttl
        self._store[(user_id, platform.value)] = (expires, message)

    async def get(self, user_id: int, platform: Platform) -> OnboardingPendingMessage | None:
        self._cleanup()
        item = self._store.get((user_id, platform.value))
        return item[1] if item else None

    async def delete(self, user_id: int, platform: Platform) -> None:
        self._cleanup()
        self._store.pop((user_id, platform.value), None)

    async def get_and_delete(self, user_id: int, platform: Platform) -> OnboardingPendingMessage | None:
        message = await self.get(user_id, platform)
        await self.delete(user_id, platform)
        return message
