import asyncio
import os
import signal
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from aiogram import Bot as TgBot, Dispatcher
from aiogram import BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject
import discord
import yaml
from discord import app_commands
from dotenv import load_dotenv

from adapters.outbound.sqlite_storage import SQLiteStorage
from adapters.outbound.openai_detector import OpenAIDetector
from adapters.outbound.nominatim_geo import NominatimGeo
from adapters.outbound.memory_pending import MemoryOnboardingPending
from adapters.outbound.memory_onboarding_chillout_state import MemoryOnboardingChilloutState
from adapters.executors.telegram_executor import TelegramCommandExecutor
from adapters.executors.discord_executor import DiscordCommandExecutor
from adapters.inbound.discord.ui import SetTimezoneView
from core.pipeline.pipeline import Pipeline
from core.domain.value_objects import BotSettings
from core.domain.enums import ResponseStyle
from core.services.delivery import DeliveryService
from core.services.message_processing import MessageProcessingService
from core.services.onboarding import OnboardingCoordinator
from core.services.profile import ProfileService
from ports.storage import StoragePort
from ports.geocoding import GeoPort

@dataclass
class AppContainer:
    storage: StoragePort
    fresh_pipeline: Pipeline
    replay_pipeline: Pipeline
    geocoder: GeoPort
    onboarding_coordinator: OnboardingCoordinator
    profile_service: ProfileService
    message_processor: MessageProcessingService

logger = logging.getLogger(__name__)


def build_settings(config_path: Path) -> BotSettings:
    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)

    bot_config = config_data.get("bot", {})
    response_style_str = bot_config.get("response_style", "block")
    style = ResponseStyle.INLINE if response_style_str.lower() == "inline_sentence" else ResponseStyle.BLOCK

    return BotSettings(
        show_usernames=bot_config.get("show_usernames", False),
        show_event_title=bot_config.get("show_event_title", True),
        response_style=style,
        max_age_fresh_secs=bot_config.get("max_age_fresh_secs", 30),
        onboarding_cooldown_secs=bot_config.get("onboarding_cooldown_secs", 3600),
        onboarding_pending_ttl_secs=bot_config.get("onboarding_pending_ttl_secs", 3600),
    )


def build_pipelines(storage, detector, geocoder, settings: BotSettings) -> tuple[Pipeline, Pipeline]:
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
        AgingStage(settings),
        DetectionStage(detector),
        GeoResolveStage(geocoder),
        HydrationStage(storage),
        FormatStage(settings),
        DecisionStage(),
    ])

    replay_pipeline = Pipeline([
        HydrationStage(storage),
        FormatStage(settings),
        DecisionStage(),
    ])
    return fresh_pipeline, replay_pipeline



async def main():
    from adapters.inbound.telegram.handlers import on_message as tg_on_message
    from adapters.inbound.telegram.onboarding_handler import router as onboarding_router
    from adapters.inbound.telegram.commands_handler import router as tg_commands_router
    from adapters.inbound.discord.events import on_message as dc_on_message
    from adapters.inbound.discord.slash_commands import setup_slash_commands

    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Timezone Bot with new Hexagonal Architecture (M2.5)")

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    dc_token = os.getenv("DISCORD_BOT_TOKEN")
    
    if not tg_token or not dc_token:
        logger.warning("Both TELEGRAM_BOT_TOKEN and DISCORD_BOT_TOKEN must be set to run both bots.")
        if not tg_token and not dc_token:
            return

    # Infrastructure Setup
    db_path = Path("data/bot.db")
    storage = SQLiteStorage(db_path)
    await storage._get_conn() 

    detector = OpenAIDetector()
    geocoder = NominatimGeo()
    settings = build_settings(Path("configuration.yaml"))

    onboarding_pending_store = MemoryOnboardingPending(
        ttl_seconds=settings.onboarding_pending_ttl_secs
    )
    onboarding_chillout_state = MemoryOnboardingChilloutState()
    fresh_pipeline, replay_pipeline = build_pipelines(storage, detector, geocoder, settings)

    tg_bot = None
    if tg_token:
        tg_bot = TgBot(token=tg_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dc_client = None
    tree = None
    if dc_token:
        intents = discord.Intents.default()
        intents.message_content = True
        dc_client = discord.Client(intents=intents)
        tree = app_commands.CommandTree(dc_client)

    onboarding_coordinator: OnboardingCoordinator | None = None

    tg_executor = TelegramCommandExecutor(bot=tg_bot) if tg_bot else None

    def _make_discord_onboarding_view(target_user_id: int) -> discord.ui.View:
        if onboarding_coordinator is None:
            raise RuntimeError("Onboarding coordinator is not initialized yet")
        return SetTimezoneView(target_user_id, onboarding_coordinator)

    dc_executor = (
        DiscordCommandExecutor(
            client=dc_client,
            onboarding_view_factory=_make_discord_onboarding_view,
        )
        if dc_client else None
    )

    delivery_service = DeliveryService(tg_executor=tg_executor, dc_executor=dc_executor)

    onboarding_coordinator = OnboardingCoordinator(
        storage_port=storage,
        onboarding_pending_port=onboarding_pending_store,
        chillout_state_port=onboarding_chillout_state,
        geocoding_port=geocoder,
        replay_pipeline=replay_pipeline,
        delivery_service=delivery_service,
        settings=settings,
    )

    message_processor = MessageProcessingService(
        fresh_pipeline=fresh_pipeline,
        storage_port=storage,
        delivery_service=delivery_service,
        onboarding_coordinator=onboarding_coordinator,
    )

    profile_service = ProfileService(storage_port=storage)

    container = AppContainer(
        storage=storage,
        fresh_pipeline=fresh_pipeline,
        replay_pipeline=replay_pipeline,
        geocoder=geocoder,
        onboarding_coordinator=onboarding_coordinator,
        profile_service=profile_service,
        message_processor=message_processor,
    )

    tasks = []

    # Setup Telegram
    if tg_token and tg_bot:
        dp = Dispatcher(storage=MemoryStorage())  # FSM needs a storage backend

        # Middleware: injects `container` into every handler that declares it
        class ContainerMiddleware(BaseMiddleware):
            async def __call__(
                self,
                handler,
                event: TelegramObject,
                data: dict[str, Any],
            ) -> Any:
                data["container"] = container
                return await handler(event, data)

        dp.update.outer_middleware(ContainerMiddleware())

        # Onboarding FSM router — must be registered BEFORE the catch-all
        dp.include_router(onboarding_router)
        dp.include_router(tg_commands_router)

        @dp.message()
        async def wrapped_tg_on_message(message):
            await tg_on_message(message, container)

        tasks.append(asyncio.create_task(dp.start_polling(tg_bot, handle_signals=False)))

    # Setup Discord
    if dc_token and dc_client and tree:

        @dc_client.event
        async def on_message(message):
            await dc_on_message(message, container)

        @dc_client.event
        async def on_ready():
            setup_slash_commands(tree, container)
            try:
                await tree.sync()
                logger.info(f"Discord slash commands synced. Logged in as {dc_client.user}")
            except Exception as e:
                logger.error(f"Failed to sync slash commands: {e}")

        tasks.append(asyncio.create_task(dc_client.start(dc_token)))

    # Custom Signal Handling
    stop_event = asyncio.Event()

    def _signal_handler():
        if not stop_event.is_set():
            logger.info("Received shutdown signal. Stopping bots gracefully...")
            stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass # add_signal_handler is not available on Windows

    try:
        if tasks:
            logger.info("Bots started polling.")
            done, pending = await asyncio.wait(
                [asyncio.create_task(stop_event.wait()), *tasks],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            if stop_event.is_set():
                if 'tg_bot' in locals() and 'dp' in locals():
                    await dp.stop_polling()
                if dc_client is not None:
                    await dc_client.close()
                logger.info("Waiting for bots to cleanly exit...")
                await asyncio.gather(*tasks, return_exceptions=True)
            else:
                logger.info("A bot stopped unexpectedly.")
        else:
            logger.info("No tasks to run.")
    finally:
        await storage.close()
        logger.info("Cleaned up infrastructure.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted (KeyboardInterrupt).")
