from abc import ABC, abstractmethod
from core.domain.commands import (
    Command,
    SaveOnboardingPending,
    MarkOnboardingPromptShown,
    NoOp,
    SendReply,
    ShowOnboarding,
)
from ports.pending import OnboardingPendingPort
from ports.onboarding_chillout_state import OnboardingChilloutStatePort
from ports.executor import CommandExecutorPort
import logging

logger = logging.getLogger(__name__)

class BaseCommandExecutor(CommandExecutorPort, ABC):
    def __init__(
        self,
        onboarding_pending_port: OnboardingPendingPort,
        onboarding_chillout_state_port: OnboardingChilloutStatePort,
    ):
        self.onboarding_pending_port = onboarding_pending_port
        self.onboarding_chillout_state_port = onboarding_chillout_state_port
        self._handlers = {
            SaveOnboardingPending: self._handle_save_onboarding_pending,
            MarkOnboardingPromptShown: self._handle_mark_onboarding_prompt_shown,
            NoOp: self._handle_noop,
            SendReply: self._handle_send_reply,
            ShowOnboarding: self._handle_show_onboarding,
        }

    async def execute(self, commands: list[Command]) -> None:
        for cmd in commands:
            handler = self._handlers.get(type(cmd))
            if handler:
                await handler(cmd)
            else:
                logger.warning(f"Unknown command type: {type(cmd)}")

    async def _handle_save_onboarding_pending(self, cmd: SaveOnboardingPending) -> None:
        await self.onboarding_pending_port.upsert(cmd.user_id, cmd.platform, cmd.message)

    async def _handle_mark_onboarding_prompt_shown(self, cmd: MarkOnboardingPromptShown) -> None:
        await self.onboarding_chillout_state_port.mark_onboarding_shown(cmd.user_id, cmd.platform)

    async def _handle_noop(self, cmd: NoOp) -> None:
        pass

    @abstractmethod
    async def _handle_send_reply(self, cmd: SendReply) -> None:
        pass

    @abstractmethod
    async def _handle_show_onboarding(self, cmd: ShowOnboarding) -> None:
        pass
