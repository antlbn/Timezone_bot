from typing import Protocol
from src.core.domain.value_objects import PendingMessage
from src.core.domain.enums import Platform

class PendingPort(Protocol):
    async def save(self, user_id: int, platform: Platform, message: PendingMessage) -> None:
        ...

    async def get_and_delete(self, user_id: int, platform: Platform) -> list[PendingMessage]:
        ...

    async def has_pending(self, user_id: int, platform: Platform) -> bool:
        """Return True if there is at least one non-expired pending message for this user.
        Used by OnboardingGateStage to enforce the cooldown window: if pending exists,
        the user was already prompted and is currently ignoring — don't re-prompt yet.
        """
        ...
