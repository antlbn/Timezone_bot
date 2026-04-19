from time import monotonic

from core.domain.enums import Platform
from ports.onboarding_chillout_state import OnboardingChilloutStatePort


class MemoryOnboardingChilloutState(OnboardingChilloutStatePort):
    def __init__(self, now_fn=None):
        self._shown_at: dict[tuple[int, str], float] = {}
        self._now = now_fn or monotonic

    async def is_onboarding_in_chillout(
        self,
        user_id: int,
        platform: Platform,
        cooldown_seconds: int,
    ) -> bool:
        shown_at = self._shown_at.get((user_id, platform.value))
        if shown_at is None:
            return False
        return (self._now() - shown_at) < cooldown_seconds

    async def mark_onboarding_shown(self, user_id: int, platform: Platform) -> None:
        self._shown_at[(user_id, platform.value)] = self._now()
