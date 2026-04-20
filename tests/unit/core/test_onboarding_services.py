from datetime import datetime, timedelta, timezone
import pytest
import dataclasses

from core.domain.commands import SendReply
from core.domain.enums import Platform
from core.domain.value_objects import BotSettings, InputData, MessageContext, MessageDecision, OnboardingPendingMessage, TimePoint
from core.pipeline.pipeline import Pipeline
from adapters.outbound.delivery_service import DeliveryService
from core.services.onboarding import OnboardingPromptService, OnboardingCompletionUseCase, OnboardingResult
from ports.detection import DetectionResult
from ports.geocoding import Location
from tests.fakes.ports import (
    FakeCommandExecutorPort,
    FakeGeoPort,
    FakeOnboardingChilloutStatePort,
    FakeOnboardingPendingPort,
    FakeStoragePort,
)

class StaticReplayStage:
    def __init__(self, decision: MessageDecision):
        self.decision = decision

    async def process(self, ctx: MessageContext) -> MessageContext:
        return dataclasses.replace(ctx, decision=self.decision)

def _pending_message(*, minutes_old: int = 0) -> OnboardingPendingMessage:
    return OnboardingPendingMessage(
        original_input=InputData(
            text="Meet at 15:00",
            user_id=1,
            platform=Platform.TELEGRAM,
            author_name="Alice",
            timestamp_utc=datetime.now(timezone.utc) - timedelta(minutes=minutes_old),
            chat_id="chat1",
            thread_id="thread-1",
        ),
        detection=DetectionResult(time_mentioned=True, points=(TimePoint(time="15:00"),)),
    )

@pytest.mark.asyncio
async def test_prompt_service_saves_pending_and_checks_chillout():
    pending_port = FakeOnboardingPendingPort()
    chillout_port = FakeOnboardingChilloutStatePort(in_chillout=False)
    settings = BotSettings(onboarding_cooldown_secs=3600)
    
    service = OnboardingPromptService(
        onboarding_pending_port=pending_port,
        chillout_state_port=chillout_port,
        settings=settings
    )
    
    message = _pending_message()
    should_prompt = await service.store_pending_and_should_prompt(1, Platform.TELEGRAM, message)
    
    assert should_prompt is True
    assert await pending_port.get(1, Platform.TELEGRAM) == message
    assert chillout_port.checked == [(1, Platform.TELEGRAM, 3600)]

@pytest.mark.asyncio
async def test_prompt_service_mark_prompt_shown():
    chillout_port = FakeOnboardingChilloutStatePort()
    service = OnboardingPromptService(
        onboarding_pending_port=FakeOnboardingPendingPort(),
        chillout_state_port=chillout_port,
        settings=BotSettings()
    )
    
    await service.mark_prompt_shown(1, Platform.TELEGRAM)
    assert chillout_port.marked == [(1, Platform.TELEGRAM)]

@pytest.mark.asyncio
async def test_completion_use_case_returns_error_if_city_not_found():
    geo = FakeGeoPort(resolves_to=None)
    storage = FakeStoragePort()
    use_case = OnboardingCompletionUseCase(
        users_repo=storage,
        onboarding_pending_port=FakeOnboardingPendingPort(),
        geocoding_port=geo,
        replay_pipeline=Pipeline([]),
        delivery_service=DeliveryService(tg_executor=FakeCommandExecutorPort()),
        settings=BotSettings()
    )
    
    result = await use_case.complete(1, "UnknownCity", Platform.TELEGRAM)
    
    assert result.ok is False
    assert result.error == "city_not_found"
    assert storage.users == {}

@pytest.mark.asyncio
async def test_completion_use_case_replays_pending_and_clears_it():
    pending_port = FakeOnboardingPendingPort()
    message = _pending_message()
    await pending_port.upsert(1, Platform.TELEGRAM, message)
    
    storage = FakeStoragePort()
    executor = FakeCommandExecutorPort()
    geo = FakeGeoPort(resolves_to=Location(city="London", timezone="Europe/London", country_code="GB", flag="🇬🇧"))
    
    use_case = OnboardingCompletionUseCase(
        users_repo=storage,
        onboarding_pending_port=pending_port,
        geocoding_port=geo,
        replay_pipeline=Pipeline([StaticReplayStage(MessageDecision(reply_text="15:00 London"))]),
        delivery_service=DeliveryService(tg_executor=executor),
        settings=BotSettings()
    )
    
    result = await use_case.complete(1, "London", Platform.TELEGRAM)
    
    assert result.ok is True
    assert storage.users[(1, Platform.TELEGRAM)].timezone == "Europe/London"
    assert executor.executed_commands == [
        SendReply(text="15:00 London", chat_id="chat1", thread_id="thread-1")
    ]
    assert await pending_port.get(1, Platform.TELEGRAM) is None

@pytest.mark.asyncio
async def test_completion_use_case_drops_stale_pending():
    pending_port = FakeOnboardingPendingPort()
    await pending_port.upsert(1, Platform.TELEGRAM, _pending_message(minutes_old=10))
    executor = FakeCommandExecutorPort()
    
    use_case = OnboardingCompletionUseCase(
        users_repo=FakeStoragePort(),
        onboarding_pending_port=pending_port,
        geocoding_port=FakeGeoPort(resolves_to=Location(city="L", timezone="T", country_code="C", flag="F")),
        replay_pipeline=Pipeline([]),
        delivery_service=DeliveryService(tg_executor=executor),
        settings=BotSettings(max_age_fresh_secs=30)
    )
    
    result = await use_case.complete(1, "London", Platform.TELEGRAM)
    
    assert result.ok is True
    assert executor.executed_commands == []
    assert await pending_port.get(1, Platform.TELEGRAM) is None

@pytest.mark.asyncio
async def test_completion_use_case_decline():
    storage = FakeStoragePort()
    pending_port = FakeOnboardingPendingPort()
    await pending_port.upsert(1, Platform.TELEGRAM, _pending_message())
    
    use_case = OnboardingCompletionUseCase(
        users_repo=storage,
        onboarding_pending_port=pending_port,
        geocoding_port=FakeGeoPort(),
        replay_pipeline=Pipeline([]),
        delivery_service=DeliveryService(tg_executor=FakeCommandExecutorPort()),
        settings=BotSettings()
    )
    
    await use_case.decline(1, Platform.TELEGRAM)
    
    assert storage.users[(1, Platform.TELEGRAM)].onboarding_declined is True
    assert await pending_port.get(1, Platform.TELEGRAM) is None
