from datetime import datetime, timezone

import pytest

from core.domain.enums import Platform
from core.domain.value_objects import BotSettings, InputData, MessageContext, OnboardingPendingMessage, TimePoint
from core.pipeline.pipeline import Pipeline
from core.services.delivery import DeliveryService
from core.services.message_processing import MessageProcessingService
from core.services.onboarding import OnboardingCoordinator
from ports.detection import DetectionResult
from ports.geocoding import Location
from tests.fakes.ports import (
    FakeCommandExecutorPort,
    FakeGeoPort,
    FakeOnboardingChilloutStatePort,
    FakeOnboardingPendingPort,
    FakeStoragePort,
)


class ExplodingStage:
    async def process(self, ctx: MessageContext) -> MessageContext:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_message_processing_ignores_pipeline_failure_without_side_effects():
    storage = FakeStoragePort()
    executor = FakeCommandExecutorPort()
    processor = MessageProcessingService(
        fresh_pipeline=Pipeline([ExplodingStage()]),
        storage_port=storage,
        delivery_service=DeliveryService(tg_executor=executor),
        onboarding_coordinator=OnboardingCoordinator(
            storage_port=storage,
            onboarding_pending_port=FakeOnboardingPendingPort(),
            chillout_state_port=FakeOnboardingChilloutStatePort(),
            geocoding_port=FakeGeoPort(),
            replay_pipeline=Pipeline([]),
            delivery_service=DeliveryService(tg_executor=executor),
            settings=BotSettings(),
        ),
    )

    await processor.process_input(
        InputData(
            text="15:00",
            user_id=1,
            platform=Platform.TELEGRAM,
            author_name="Alice",
            timestamp_utc=datetime.now(timezone.utc),
            chat_id="chat1",
        )
    )

    assert storage.created == []
    assert executor.executed_commands == []


@pytest.mark.asyncio
async def test_onboarding_complete_clears_pending_when_replay_pipeline_fails():
    storage = FakeStoragePort()
    pending = FakeOnboardingPendingPort()
    executor = FakeCommandExecutorPort()
    coordinator = OnboardingCoordinator(
        storage_port=storage,
        onboarding_pending_port=pending,
        chillout_state_port=FakeOnboardingChilloutStatePort(),
        geocoding_port=FakeGeoPort(
            resolves_to=Location(city="London", timezone="Europe/London", country_code="GB", flag="🇬🇧")
        ),
        replay_pipeline=Pipeline([ExplodingStage()]),
        delivery_service=DeliveryService(tg_executor=executor),
        settings=BotSettings(),
    )

    await pending.upsert(
        1,
        Platform.TELEGRAM,
        OnboardingPendingMessage(
            original_input=InputData(
                text="15:00",
                user_id=1,
                platform=Platform.TELEGRAM,
                author_name="Alice",
                timestamp_utc=datetime.now(timezone.utc),
                chat_id="chat1",
            ),
            detection=DetectionResult(time_mentioned=True, points=(TimePoint(time="15:00"),)),
        ),
    )

    result = await coordinator.complete(1, "London", Platform.TELEGRAM)

    assert result.ok is True
    assert executor.executed_commands == []
    assert await pending.get(1, Platform.TELEGRAM) is None
