from __future__ import annotations

from typing import TYPE_CHECKING

from core.domain.commands import SendReply, ShowOnboarding
from core.domain.value_objects import InputData, MessageContext, MessageDecision
from core.pipeline.pipeline import Pipeline
from ports.repositories import UserRepositoryPort, ChatRepositoryPort

if TYPE_CHECKING:
    from ports.delivery import DeliveryPort
from core.services.onboarding import OnboardingPromptService


class MessageProcessingService:
    """Application service for fresh inbound messages.

    The pipeline computes a MessageDecision; this service applies workflow
    side effects and emits delivery commands.
    """

    def __init__(
        self,
        fresh_pipeline: Pipeline,
        users_repo: UserRepositoryPort,
        chats_repo: ChatRepositoryPort,
        delivery_service: "DeliveryPort",
        onboarding_prompt: "OnboardingPromptService",
    ) -> None:
        self._fresh_pipeline = fresh_pipeline
        self._users = users_repo
        self._chats = chats_repo
        self._delivery = delivery_service
        self._onboarding = onboarding_prompt

    async def process_input(self, data: InputData) -> None:
        ctx = MessageContext(input=data)
        ctx = await self._fresh_pipeline.run(ctx)
        await self._register_message_participant(ctx)
        await self._apply_decision(data, ctx.decision)

    async def _register_message_participant(self, ctx: MessageContext) -> None:
        """Sync sender/chat metadata only for messages that actually contain a detected time."""
        if not ctx.detection or not ctx.detection.time_mentioned:
            return

        await self._users.ensure_user_metadata(
            ctx.input.user_id,
            ctx.input.platform,
            ctx.input.author_name,
        )

        if ctx.input.chat_id:
            await self._chats.add_chat_member(
                chat_id=ctx.input.chat_id,
                user_id=ctx.input.user_id,
                platform=ctx.input.platform,
            )

    async def _apply_decision(self, data: InputData, decision: MessageDecision | None) -> None:
        if decision is None or decision.ignore:
            return

        commands = []
        if decision.reply_text:
            commands.append(
                SendReply(
                    text=decision.reply_text,
                    chat_id=data.chat_id,
                    thread_id=data.thread_id,
                )
            )

        prompt_shown = False
        if decision.needs_onboarding and decision.pending_message is not None:
            prompt_shown = await self._onboarding.store_pending_and_should_prompt(
                user_id=data.user_id,
                platform=data.platform,
                pending_message=decision.pending_message,
            )
            if prompt_shown:
                commands.append(
                    ShowOnboarding(
                        user_id=data.user_id,
                        author_name=data.author_name,
                        chat_id=data.chat_id,
                        thread_id=data.thread_id,
                    )
                )

        await self._delivery.deliver(data.platform, commands)

        if prompt_shown:
            await self._onboarding.mark_prompt_shown(data.user_id, data.platform)
