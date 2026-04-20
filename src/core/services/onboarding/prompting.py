from core.domain.enums import Platform
from core.domain.value_objects import OnboardingPendingMessage, BotSettings
from ports.onboarding_chillout_state import OnboardingChilloutStatePort
from ports.pending import OnboardingPendingPort

class OnboardingPromptService:
    """Manages the decision to prompt a user for timezone onboarding.
    
    Responsible only for the incoming flow: saving the pending message
    and deciding if the user should be prompted based on cooldown settings.
    """
    def __init__(
        self,
        onboarding_pending_port: OnboardingPendingPort,
        chillout_state_port: OnboardingChilloutStatePort,
        settings: BotSettings,
    ) -> None:
        self._onboarding_pending = onboarding_pending_port
        self._chillout_state = chillout_state_port
        self._settings = settings

    async def store_pending_and_should_prompt(
        self,
        user_id: int,
        platform: Platform,
        pending_message: OnboardingPendingMessage,
    ) -> bool:
        """Store the latest pending message and decide whether the onboarding prompt should be shown."""
        await self._onboarding_pending.upsert(user_id, platform, pending_message)
        return not await self._chillout_state.is_onboarding_in_chillout(
            user_id,
            platform,
            self._settings.onboarding_cooldown_secs,
        )

    async def mark_prompt_shown(self, user_id: int, platform: Platform) -> None:
        await self._chillout_state.mark_onboarding_shown(user_id, platform)
