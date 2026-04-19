from typing import Protocol

from core.domain.enums import Platform


class OnboardingChilloutStatePort(Protocol):
    async def is_onboarding_in_chillout(
        self,
        user_id: int,
        platform: Platform,
        cooldown_seconds: int,
    ) -> bool:
        ...

    async def mark_onboarding_shown(self, user_id: int, platform: Platform) -> None:
        ...
