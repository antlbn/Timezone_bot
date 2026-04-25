from time import monotonic

from core.domain.enums import Platform
from core.domain.value_objects import OnboardingPendingMessage
from ports.pending import OnboardingPendingPort

class MemoryOnboardingPending(OnboardingPendingPort):
    """In-memory store for the latest onboarding-pending message per chat."""
    def __init__(self, ttl_seconds: int = 3600, now_fn=None):
        # (user_id, platform_value, chat_id) -> (expires_at, message)
        self._store: dict[tuple[int, str, str], tuple[float, OnboardingPendingMessage]] = {}
        self.ttl = ttl_seconds
        self._now = now_fn or monotonic

    def _cleanup(self):
        now = self._now()
        for key in list(self._store.keys()):
            expires, _ = self._store[key]
            if expires <= now:
                del self._store[key]

    async def upsert(
        self,
        user_id: int,
        platform: Platform,
        chat_id: str,
        message: OnboardingPendingMessage,
    ) -> None:
        self._cleanup()
        expires = self._now() + self.ttl
        self._store[(user_id, platform.value, chat_id)] = (expires, message)

    async def get(
        self,
        user_id: int,
        platform: Platform,
        chat_id: str,
    ) -> OnboardingPendingMessage | None:
        self._cleanup()
        item = self._store.get((user_id, platform.value, chat_id))
        return item[1] if item else None

    async def list_for_user(self, user_id: int, platform: Platform) -> list[OnboardingPendingMessage]:
        self._cleanup()
        items = []
        for (stored_user_id, stored_platform, _chat_id), (_expires, message) in self._store.items():
            if stored_user_id == user_id and stored_platform == platform.value:
                items.append(message)
        return items

    async def delete(self, user_id: int, platform: Platform, chat_id: str) -> None:
        self._cleanup()
        self._store.pop((user_id, platform.value, chat_id), None)
