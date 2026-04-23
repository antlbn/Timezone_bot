import logging
from pathlib import Path
from dataclasses import dataclass

from adapters.outbound.sqlite_storage import SQLiteStorage
from adapters.outbound.openai_detector import OpenAIDetector
from adapters.outbound.nominatim_geo import NominatimGeo
from adapters.outbound.memory_pending import MemoryOnboardingPending
from adapters.outbound.memory_onboarding_chillout_state import MemoryOnboardingChilloutState
from adapters.outbound.delivery_service import DeliveryService
from adapters.outbound.real_time import RealTimeAdapter

from core.pipeline.pipeline import Pipeline
from core.services.message_processing import MessageProcessingService
from core.services.onboarding import OnboardingPromptService, OnboardingCompletionUseCase
from core.services.profile import ProfileService
from ports.repositories import UserRepositoryPort, ChatRepositoryPort
from ports.geocoding import GeoPort

from aiogram import Bot as TgBot
import discord
from discord import app_commands
from adapters.inbound.discord.ui import SetTimezoneView
from adapters.executors.telegram_executor import TelegramCommandExecutor
from adapters.executors.discord_executor import DiscordCommandExecutor

from config import AppConfig

logger = logging.getLogger(__name__)

@dataclass
class AppContainer:
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

def build_pipelines(storage, detector, geocoder, settings, time_port) -> tuple[Pipeline, Pipeline]:
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
        GuardStage(),
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

async def build_container(
    config: AppConfig,
    tg_bot: TgBot | None = None,
    tg_username: str | None = None,
    dc_client: discord.Client | None = None,
) -> AppContainer:
    # Infrastructure Setup
    db_path = Path("data/bot.db")
    storage = SQLiteStorage(db_path)
    await storage.initialize()

    time_port = RealTimeAdapter()
    detector = OpenAIDetector(config=config.llm)
    geocoder = NominatimGeo()
    
    onboarding_pending_store = MemoryOnboardingPending(
        ttl_seconds=config.bot.onboarding_pending_ttl_secs
    )
    onboarding_chillout_state = MemoryOnboardingChilloutState()
    
    fresh_pipeline, replay_pipeline = build_pipelines(
        storage, detector, geocoder, config.bot, time_port
    )

    # Executors
    tg_executor = (
        TelegramCommandExecutor(bot=tg_bot, bot_username=tg_username, config=config.telegram)
        if (tg_bot and tg_username) else None
    )

    onboarding_completion_holder = [None] # For circular ref in dc_executor

    def _make_discord_onboarding_view(target_user_id: int) -> discord.ui.View:
        if onboarding_completion_holder[0] is None:
            raise RuntimeError("Onboarding completion use case is not initialized yet")
        return SetTimezoneView(target_user_id, onboarding_completion_holder[0])

    dc_executor = (
        DiscordCommandExecutor(client=dc_client, onboarding_view_factory=_make_discord_onboarding_view)
        if dc_client else None
    )

    # Services
    delivery_service = DeliveryService(tg_executor=tg_executor, dc_executor=dc_executor)

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
        settings=config.bot,
        time_port=time_port,
    )
    onboarding_completion_holder[0] = onboarding_completion

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
        users_repo=storage,
        chats_repo=storage,
        fresh_pipeline=fresh_pipeline,
        replay_pipeline=replay_pipeline,
        geocoder=geocoder,
        onboarding_prompt=onboarding_prompt,
        onboarding_completion=onboarding_completion,
        profile_service=profile_service,
        message_processor=message_processor,
        delivery_service=delivery_service
    )
