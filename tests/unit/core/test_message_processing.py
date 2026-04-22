from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from core.domain.commands import SendReply, ShowOnboarding
from core.domain.enums import Platform
from core.domain.value_objects import BotSettings, InputData, MessageContext, MessageDecision, OnboardingPendingMessage, TimePoint
from core.pipeline.pipeline import Pipeline
from adapters.outbound.delivery_service import DeliveryService
from core.services.message_processing import MessageProcessingService
from ports.detection import DetectionResult
from tests.fakes.ports import (
    FakeCommandExecutorPort,
    FakeStoragePort,
)


@dataclass
class StaticDecisionStage:
    decision: MessageDecision | None
    detection: DetectionResult | None = None

    async def process(self, ctx: MessageContext) -> MessageContext:
        import dataclasses
        return dataclasses.replace(ctx, detection=self.detection, decision=self.decision)


class FakeOnboardingPromptService:
    def __init__(self, should_prompt: bool = False):
        self.should_prompt = should_prompt
        self.pending_calls: list[tuple[int, Platform, OnboardingPendingMessage]] = []
        self.marked: list[tuple[int, Platform]] = []

    async def store_pending_and_should_prompt(
        self,
        user_id: int,
        platform: Platform,
        pending_message: OnboardingPendingMessage,
    ) -> bool:
        self.pending_calls.append((user_id, platform, pending_message))
        return self.should_prompt

    async def mark_prompt_shown(self, user_id: int, platform: Platform) -> None:
        self.marked.append((user_id, platform))


def _input() -> InputData:
    return InputData(
        text="Meeting at 15:00",
        user_id=1,
        platform=Platform.TELEGRAM,
        author_name="Alice",
        timestamp_utc=datetime.now(timezone.utc),
        chat_id="chat1",
        thread_id="thread-1",
    )


def _pending_message(data: InputData) -> OnboardingPendingMessage:
    return OnboardingPendingMessage(
        original_input=data,
        detection=DetectionResult(time_mentioned=True, points=(TimePoint(time="15:00"),)),
    )


@pytest.mark.asyncio
async def test_process_input_registers_and_sends_reply_for_detected_message():
    data = _input()
    storage = FakeStoragePort()
    executor = FakeCommandExecutorPort()
    service = MessageProcessingService(
        fresh_pipeline=Pipeline([
            StaticDecisionStage(
                decision=MessageDecision(reply_text="15:00 Berlin"),
                detection=DetectionResult(time_mentioned=True, points=(TimePoint(time="15:00"),)),
            )
        ]),
        users_repo=storage, chats_repo=storage,
        delivery_service=DeliveryService(tg_executor=executor),
        onboarding_prompt=FakeOnboardingPromptService(),
        settings=BotSettings(),
    )

    await service.process_input(data)

    assert (1, Platform.TELEGRAM, "Alice") in storage.created
    assert len(executor.executed_commands) == 1
    assert executor.executed_commands[0] == SendReply(
        text="15:00 Berlin",
        chat_id="chat1",
        thread_id="thread-1",
    )


@pytest.mark.asyncio
async def test_process_input_skips_registration_and_delivery_when_no_detection():
    data = _input()
    storage = FakeStoragePort()
    executor = FakeCommandExecutorPort()
    service = MessageProcessingService(
        fresh_pipeline=Pipeline([
            StaticDecisionStage(decision=MessageDecision(ignore=True), detection=None)
        ]),
        users_repo=storage, chats_repo=storage,
        delivery_service=DeliveryService(tg_executor=executor),
        onboarding_prompt=FakeOnboardingPromptService(),
        settings=BotSettings(),
    )

    await service.process_input(data)

    assert storage.created == []
    assert executor.executed_commands == []


@pytest.mark.asyncio
async def test_process_input_updates_pending_and_marks_prompt_when_onboarding_should_be_shown():
    data = _input()
    storage = FakeStoragePort()
    executor = FakeCommandExecutorPort()
    onboarding = FakeOnboardingPromptService(should_prompt=True)
    pending = _pending_message(data)
    service = MessageProcessingService(
        fresh_pipeline=Pipeline([
            StaticDecisionStage(
                decision=MessageDecision(needs_onboarding=True, pending_message=pending),
                detection=pending.detection,
            )
        ]),
        users_repo=storage, chats_repo=storage,
        delivery_service=DeliveryService(tg_executor=executor),
        onboarding_prompt=onboarding,
        settings=BotSettings(),
    )

    await service.process_input(data)

    assert len(onboarding.pending_calls) == 1
    assert onboarding.pending_calls[0][2] == pending
    assert onboarding.marked == [(1, Platform.TELEGRAM)]
    assert executor.executed_commands == [
        ShowOnboarding(
            user_id=1,
            author_name="Alice",
            chat_id="chat1",
            thread_id="thread-1",
        )
    ]


@pytest.mark.asyncio
async def test_process_input_updates_pending_without_mark_when_chillout_active():
    data = _input()
    executor = FakeCommandExecutorPort()
    onboarding = FakeOnboardingPromptService(should_prompt=False)
    pending = _pending_message(data)
    service = MessageProcessingService(
        fresh_pipeline=Pipeline([
            StaticDecisionStage(
                decision=MessageDecision(needs_onboarding=True, pending_message=pending),
                detection=pending.detection,
            )
        ]),
        users_repo=FakeStoragePort(), chats_repo=FakeStoragePort(),
        delivery_service=DeliveryService(tg_executor=executor),
        onboarding_prompt=onboarding,
        settings=BotSettings(),
    )

    await service.process_input(data)

    assert len(onboarding.pending_calls) == 1
    assert onboarding.marked == []
    assert executor.executed_commands == []
