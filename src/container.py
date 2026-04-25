import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Protocol, TYPE_CHECKING

from aiogram import Bot as TgBot
import discord

if TYPE_CHECKING:
    from adapters.inbound.telegram.common import DeletionScheduler

from adapters.inbound.telegram.config import TelegramConfig
from adapters.executors.discord_executor import DiscordCommandExecutor
from adapters.executors.telegram_executor import TelegramCommandExecutor
from adapters.inbound.discord.ui import SetTimezoneView
from adapters.outbound.sqlite_storage import SQLiteStorage
from adapters.outbound.openai_detector import OpenAIDetector
from adapters.outbound.nominatim_geo import NominatimGeo
from adapters.outbound.memory_pending import MemoryOnboardingPending
from adapters.outbound.memory_onboarding_chillout_state import MemoryOnboardingChilloutState
from adapters.outbound.delivery_service import DeliveryService
from adapters.outbound.real_time import RealTimeAdapter

from core.domain.enums import Platform
from core.domain.value_objects import BotSettings, LLMConfig
from core.pipeline.pipeline import Pipeline
from core.services.message_processing import MessageProcessingService
from core.services.onboarding import OnboardingPromptService, OnboardingCompletionUseCase
from core.services.profile import ProfileService
from ports.detection import DetectionPort
from ports.delivery import DeliveryPort
from ports.repositories import UserRepositoryPort, ChatRepositoryPort
from ports.geocoding import GeoPort
from ports.time import TimePort

from config import AppConfig

logger = logging.getLogger(__name__)


class StoragePorts(UserRepositoryPort, ChatRepositoryPort, Protocol):
    pass

class Closeable(Protocol):
    async def close(self) -> None: ...

@dataclass
class AppContainer:
    storage: Closeable
    users_repo: UserRepositoryPort
    chats_repo: ChatRepositoryPort
    fresh_pipeline: Pipeline
    replay_pipeline: Pipeline
    geocoder: GeoPort
    onboarding_prompt: OnboardingPromptService
    onboarding_completion: OnboardingCompletionUseCase
    profile_service: ProfileService
    message_processor: MessageProcessingService
    delivery_service: DeliveryService
    deletion_scheduler: 'DeletionScheduler'

def build_pipelines(
    storage: StoragePorts,
    detector: DetectionPort,
    geocoder: GeoPort,
    settings: BotSettings,
    time_port: TimePort,
) -> tuple[Pipeline, Pipeline]:
    from core.pipeline.stages import (
        GuardStage,
        AgingStage,
        DetectionStage,
        GeoResolveStage,
        HydrationStage,
        FormatStage,
        DecisionStage,
    )

    fresh_pipeline = Pipeline([
        GuardStage(settings),
        AgingStage(settings, time_port),
        DetectionStage(detector),
        GeoResolveStage(geocoder),
        HydrationStage(storage, storage),
        FormatStage(settings),
        DecisionStage(),
    ])

    replay_pipeline = Pipeline([
        HydrationStage(storage, storage),
        FormatStage(settings),
        DecisionStage(),
    ])
    return fresh_pipeline, replay_pipeline


def _build_tg_executor(
    tg_bot: TgBot | None,
    tg_username: str | None,
    config: TelegramConfig,
    deletion_scheduler: 'DeletionScheduler'
) -> TelegramCommandExecutor | None:
    if not tg_bot or not tg_username:
        return None
    return TelegramCommandExecutor(bot=tg_bot, bot_username=tg_username, config=config, deletion_scheduler=deletion_scheduler)


def _register_discord_executor(
    delivery_service: DeliveryService,
    dc_client: discord.Client | None,
    onboarding_completion: OnboardingCompletionUseCase,
) -> None:
    if dc_client is None:
        return

    def _make_discord_onboarding_view(target_user_id: int) -> discord.ui.View:
        return SetTimezoneView(target_user_id, onboarding_completion)

    dc_executor = DiscordCommandExecutor(
        client=dc_client,
        onboarding_view_factory=_make_discord_onboarding_view,
    )
    delivery_service.register_executor(Platform.DISCORD, dc_executor)

async def build_container(
    config: AppConfig,
    tg_bot: TgBot | None = None,
    tg_username: str | None = None,
    dc_client: discord.Client | None = None,
) -> AppContainer:
    db_path = Path("data/bot.db")
    storage = SQLiteStorage(db_path)
    await storage.initialize()

    time_port: TimePort = RealTimeAdapter()
    detector: DetectionPort = OpenAIDetector(config=config.llm, log_prompts=config.log_prompts)
    geocoder: GeoPort = NominatimGeo()

    from adapters.inbound.telegram.common import DeletionScheduler
    deletion_scheduler = DeletionScheduler()

    onboarding_pending_store = MemoryOnboardingPending(
        ttl_seconds=config.bot.onboarding_pending_ttl_secs
    )
    onboarding_chillout_state = MemoryOnboardingChilloutState()
    
    fresh_pipeline, replay_pipeline = build_pipelines(
        storage, detector, geocoder, config.bot, time_port
    )

    tg_executor = _build_tg_executor(tg_bot, tg_username, config.telegram, deletion_scheduler)
    delivery_service = DeliveryService(tg_executor=tg_executor)

    onboarding_prompt = OnboardingPromptService(
        onboarding_pending_port=onboarding_pending_store,
        chillout_state_port=onboarding_chillout_state,
        settings=config.bot,
    )

    onboarding_completion = OnboardingCompletionUseCase(
        users_repo=storage,
        chats_repo=storage,
        onboarding_pending_port=onboarding_pending_store,
        geocoding_port=geocoder,
        replay_pipeline=replay_pipeline,
        delivery_service=delivery_service,
    )

    _register_discord_executor(delivery_service, dc_client, onboarding_completion)

    message_processor = MessageProcessingService(
        fresh_pipeline=fresh_pipeline,
        users_repo=storage,
        chats_repo=storage,
        delivery_service=delivery_service,
        onboarding_prompt=onboarding_prompt,
        settings=config.bot,
    )

    profile_service = ProfileService(users_repo=storage, chats_repo=storage, time_port=time_port)

    return AppContainer(
        storage=storage,
        users_repo=storage,
        chats_repo=storage,
        fresh_pipeline=fresh_pipeline,
        replay_pipeline=replay_pipeline,
        geocoder=geocoder,
        onboarding_prompt=onboarding_prompt,
        onboarding_completion=onboarding_completion,
        profile_service=profile_service,
        message_processor=message_processor,
        delivery_service=delivery_service,
        deletion_scheduler=deletion_scheduler,
    )
