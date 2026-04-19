import asyncio
import os
import signal
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.services.dispatcher import MessageDispatcher
from aiogram import Bot as TgBot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
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
from core.pipeline.pipeline import Pipeline
from core.domain.value_objects import BotSettings
from core.domain.enums import ResponseStyle
from core.services.onboarding import OnboardingService
from core.services.profile import ProfileService
from ports.storage import StoragePort
from ports.geocoding import GeoPort

@dataclass
class AppContainer:
    storage: StoragePort
    fresh_pipeline: Pipeline
    replay_pipeline: Pipeline
    geocoder: GeoPort
    onboarding_service: OnboardingService
    profile_service: ProfileService
    dispatcher: 'MessageDispatcher'
    tg_executor: TelegramCommandExecutor | None = None
    dc_executor: DiscordCommandExecutor | None = None

logger = logging.getLogger(__name__)



async def main():
    # Deferred imports to avoid circular dependency since AppContainer is now in main.py
    from adapters.inbound.telegram.handlers import on_message as tg_on_message
    from adapters.inbound.telegram.onboarding_handler import router as onboarding_router
    from adapters.inbound.telegram.commands_handler import router as tg_commands_router
    from adapters.inbound.discord.events import on_message as dc_on_message
    from adapters.inbound.discord.slash_commands import setup_slash_commands
    from core.pipeline.stages import (
        GuardStage, AgingStage, DetectionStage, GeoResolveStage,
        RegistrationStage, HydrationStage, OnboardingChilloutStage,
        FormatStage, CommandFactoryStage,
    )

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
    # Load configuration
    config_path = Path("configuration.yaml")
    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)

    bot_config = config_data.get("bot", {})
    response_style_str = bot_config.get("response_style", "block")

    if response_style_str.lower() == "inline_sentence":
        style = ResponseStyle.INLINE
    else:
        style = ResponseStyle.BLOCK

    settings = BotSettings(
        show_usernames=bot_config.get("show_usernames", False),
        show_event_title=bot_config.get("show_event_title", True),
        response_style=style,
        max_age_fresh_secs=bot_config.get("max_age_fresh_secs", 30),
        onboarding_cooldown_secs=bot_config.get("onboarding_cooldown_secs", 3600),
        onboarding_pending_ttl_secs=bot_config.get("onboarding_pending_ttl_secs", 3600),
    )

    onboarding_pending_store = MemoryOnboardingPending(
        ttl_seconds=settings.onboarding_pending_ttl_secs
    )
    onboarding_chillout_state = MemoryOnboardingChilloutState()

    # Fresh pipeline: full processing flow for inbound messages
    fresh_pipeline = Pipeline([
        GuardStage(),
        AgingStage(settings),
        DetectionStage(detector),
        GeoResolveStage(geocoder),
        RegistrationStage(storage),
        HydrationStage(storage),
        OnboardingChilloutStage(onboarding_chillout_state, settings),
        FormatStage(settings),
        CommandFactoryStage(),
    ])

    # Replay pipeline: resumed computation after onboarding completes.
    # ctx.detection is pre-loaded from OnboardingPendingMessage by MessageDispatcher.process_pending.
    replay_pipeline = Pipeline([
        HydrationStage(storage),
        FormatStage(settings),
        CommandFactoryStage(),
    ])

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

    from core.services.dispatcher import MessageDispatcher

    tg_executor = (
        TelegramCommandExecutor(
            onboarding_pending_port=onboarding_pending_store,
            onboarding_chillout_state_port=onboarding_chillout_state,
            bot=tg_bot,
        )
        if tg_bot else None
    )
    dc_executor = (
        DiscordCommandExecutor(
            onboarding_pending_port=onboarding_pending_store,
            onboarding_chillout_state_port=onboarding_chillout_state,
            client=dc_client,
        )
        if dc_client else None
    )

    dispatcher = MessageDispatcher(
        fresh_pipeline=fresh_pipeline,
        replay_pipeline=replay_pipeline,
        tg_executor=tg_executor,
        dc_executor=dc_executor,
    )

    onboarding_service = OnboardingService(
        storage_port=storage,
        onboarding_pending_port=onboarding_pending_store,
        geocoding_port=geocoder,
        dispatcher=dispatcher,
    )
    
    profile_service = ProfileService(storage_port=storage)

    if dc_executor:
        dc_executor.set_onboarding_service(onboarding_service)

    container = AppContainer(
        storage=storage,
        fresh_pipeline=fresh_pipeline,
        replay_pipeline=replay_pipeline,
        geocoder=geocoder,
        onboarding_service=onboarding_service,
        profile_service=profile_service,
        dispatcher=dispatcher,
    )
    container.tg_executor = tg_executor
    container.dc_executor = dc_executor

    tasks = []

    # Setup Telegram
    if tg_token and tg_bot:
        dp = Dispatcher(storage=MemoryStorage())  # FSM needs a storage backend

        # Middleware: injects `container` into every handler that declares it
        @dp.update.outer_middleware()
        async def container_middleware(handler, event: Update, data: dict):
            data["container"] = container
            return await handler(event, data)

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
                if 'dc_client' in locals():
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
