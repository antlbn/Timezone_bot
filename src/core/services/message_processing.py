from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.domain.commands import Command, CommandResult, SendReply, ShowOnboarding
from core.domain.value_objects import InputData, MessageContext, BotSettings
from core.pipeline.pipeline import Pipeline
from ports.repositories import UserRepositoryPort, ChatRepositoryPort
from ports.delivery import DeliveryPort
from core.services.onboarding import OnboardingPromptService

logger = logging.getLogger(__name__)


class MessageProcessingService:
    """Application service for fresh inbound messages.

    The pipeline computes the message outcome in MessageContext; this service
    applies workflow side effects and emits delivery commands.
    """

    def __init__(
        self,
        fresh_pipeline: Pipeline,
        users_repo: UserRepositoryPort,
        chats_repo: ChatRepositoryPort,
        delivery_service: "DeliveryPort",
        onboarding_prompt: "OnboardingPromptService",
        settings: BotSettings,
    ) -> None:
        self._fresh_pipeline = fresh_pipeline
        self._users = users_repo
        self._chats = chats_repo
        self._delivery = delivery_service
        self._onboarding = onboarding_prompt
        self._settings = settings

    async def process_input(self, data: InputData) -> None:
        ctx = MessageContext(input=data)
        ctx = await self._fresh_pipeline.run(ctx)
        await self._register_message_participant(ctx)
        await self._apply_outcome(ctx)

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

    async def _apply_outcome(self, ctx: MessageContext) -> None:
        if ctx.failed:
            if ctx.failed.category == "transient":
                await self._delivery.deliver(
                    ctx.input.platform,
                    [SendReply(
                        text="⚠️ Temporary issue processing time. Please try again later.",
                        chat_id=ctx.input.chat_id,
                        thread_id=ctx.input.thread_id,
                    )]
                )
            return
        if ctx.ignore:
            return

        commands: list[Command] = []
        if ctx.reply_text:
            commands.append(
                SendReply(
                    text=ctx.reply_text,
                    chat_id=ctx.input.chat_id,
                    thread_id=ctx.input.thread_id,
                )
            )

        prompt_shown = False
        if ctx.needs_onboarding and ctx.pending_message is not None:
            prompt_shown = await self._onboarding.store_pending_and_should_prompt(
                user_id=ctx.input.user_id,
                platform=ctx.input.platform,
                pending_message=ctx.pending_message,
            )
            if prompt_shown:
                commands.append(
                    ShowOnboarding(
                        user_id=ctx.input.user_id,
                        author_name=ctx.input.author_name,
                        chat_id=ctx.input.chat_id,
                        thread_id=ctx.input.thread_id,
                    )
                )

        await self._delivery.deliver_and_log(
            ctx.input.platform, 
            commands, 
            user_id=ctx.input.user_id, 
            chat_id=ctx.input.chat_id
        )

        if prompt_shown:
            await self._onboarding.mark_prompt_shown(ctx.input.user_id, ctx.input.platform)
