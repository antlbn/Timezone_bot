import asyncio
import os
import signal
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from aiogram import Bot as TgBot, Dispatcher, Router
from aiogram import BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, Message
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
from adapters.inbound.telegram.config import TelegramConfig
from adapters.executors.discord_executor import DiscordCommandExecutor
from adapters.inbound.discord.ui import SetTimezoneView
from core.pipeline.pipeline import Pipeline
from core.domain.value_objects import BotSettings, LLMConfig, LLMModelConfig
from core.domain.enums import ResponseStyle
from adapters.outbound.delivery_service import DeliveryService
from core.services.message_processing import MessageProcessingService
from core.services.onboarding import OnboardingPromptService, OnboardingCompletionUseCase
from core.services.profile import ProfileService
from ports.repositories import UserRepositoryPort, ChatRepositoryPort
from ports.geocoding import GeoPort

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

logger = logging.getLogger(__name__)


def build_settings(config_data: dict) -> BotSettings:
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

def build_tg_config(config_data: dict) -> TelegramConfig:
    bot_config = config_data.get("bot", {})
    return TelegramConfig(
        delete_delay=bot_config.get("group_auto_delete_delay_secs", 20),
    )


def build_pipelines(storage, detector, geocoder, settings: BotSettings, time_port) -> tuple[Pipeline, Pipeline]:
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
    
    if not tg_token:
        logger.warning("TELEGRAM_BOT_TOKEN not found. Telegram bot will be disabled.")
    if not dc_token:
        logger.warning("DISCORD_BOT_TOKEN not found. Discord bot will be disabled.")
    
    if not tg_token and not dc_token:
        logger.error("No bot tokens found. Neither Telegram nor Discord can be started. Exiting.")
        return

    from adapters.outbound.real_time import RealTimeAdapter

    # Infrastructure Setup
    db_path = Path("data/bot.db")
    storage = SQLiteStorage(db_path)
    await storage.initialize()

    time_port = RealTimeAdapter()

    primary_llm = LLMModelConfig(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        model=os.getenv("LLM_MODEL", "gemini-3-flash-lite-preview")
    )
    fallback_llm = None
    if os.getenv("LLM_FALLBACK_API_KEY"):
        fallback_llm = LLMModelConfig(
            api_key=os.getenv("LLM_FALLBACK_API_KEY"),
            base_url=os.getenv("LLM_FALLBACK_BASE_URL"),
            model=os.getenv("LLM_FALLBACK_MODEL", "llama-3.1-8b-instant")
        )
    
    llm_config = LLMConfig(primary=primary_llm, fallback=fallback_llm)
    with open(Path("configuration.yaml"), "r") as f:
        config_data = yaml.safe_load(f)
    
    detector = OpenAIDetector(config=llm_config)
    geocoder = NominatimGeo()
    settings = build_settings(config_data)
    tg_config = build_tg_config(config_data)

    onboarding_pending_store = MemoryOnboardingPending(
        ttl_seconds=settings.onboarding_pending_ttl_secs
    )
    onboarding_chillout_state = MemoryOnboardingChilloutState()
    fresh_pipeline, replay_pipeline = build_pipelines(storage, detector, geocoder, settings, time_port)

    tg_bot = None
    tg_username = None
    if tg_token:
        tg_bot = TgBot(token=tg_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        me = await tg_bot.get_me()
        tg_username = me.username

    dc_client = None
    tree = None
    if dc_token:
        intents = discord.Intents.default()
        intents.message_content = True
        dc_client = discord.Client(intents=intents)
        tree = app_commands.CommandTree(dc_client)

    onboarding_completion: OnboardingCompletionUseCase | None = None

    tg_executor = (
        TelegramCommandExecutor(
            bot=tg_bot,
            bot_username=tg_username,
            config=tg_config
        )
        if (tg_bot and tg_username) else None
    )

    def _make_discord_onboarding_view(target_user_id: int) -> discord.ui.View:
        if onboarding_completion is None:
            raise RuntimeError("Onboarding completion use case is not initialized yet")
        return SetTimezoneView(target_user_id, onboarding_completion)

    dc_executor = (
        DiscordCommandExecutor(
            client=dc_client,
            onboarding_view_factory=_make_discord_onboarding_view,
        )
        if dc_client else None
    )

    delivery_service = DeliveryService(tg_executor=tg_executor, dc_executor=dc_executor)

    onboarding_prompt = OnboardingPromptService(
        onboarding_pending_port=onboarding_pending_store,
        chillout_state_port=onboarding_chillout_state,
        settings=settings,
    )

    onboarding_completion = OnboardingCompletionUseCase(
        users_repo=storage,
        chats_repo=storage,
        onboarding_pending_port=onboarding_pending_store,
        geocoding_port=geocoder,
        replay_pipeline=replay_pipeline,
        delivery_service=delivery_service,
        settings=settings,
        time_port=time_port,
    )

    message_processor = MessageProcessingService(
        fresh_pipeline=fresh_pipeline,
        users_repo=storage,
        chats_repo=storage,
        delivery_service=delivery_service,
        onboarding_prompt=onboarding_prompt,
        settings=settings,
    )

    profile_service = ProfileService(users_repo=storage, chats_repo=storage, time_port=time_port)

    container = AppContainer(
        users_repo=storage,
        chats_repo=storage,
        fresh_pipeline=fresh_pipeline,
        replay_pipeline=replay_pipeline,
        geocoder=geocoder,
        onboarding_prompt=onboarding_prompt,
        onboarding_completion=onboarding_completion,
        profile_service=profile_service,
        message_processor=message_processor,
    )

    tasks = []

    # Setup Telegram
    if tg_token and tg_bot:
        dp = Dispatcher(storage=MemoryStorage())  # FSM needs a storage backend

        # Middleware: injects `container` into every handler that declares it
        class DependencyMiddleware(BaseMiddleware):
            async def __call__(
                self,
                handler,
                event: TelegramObject,
                data: dict[str, Any],
            ) -> Any:
                data["onboarding_completion"] = container.onboarding_completion
                data["profile_service"] = container.profile_service
                data["message_processor"] = container.message_processor
                data["tg_config"] = tg_config
                return await handler(event, data)

        from adapters.inbound.telegram.middlewares import ErrorHandlingMiddleware
        dp.update.outer_middleware(ErrorHandlingMiddleware())
        dp.update.outer_middleware(DependencyMiddleware())

        from adapters.inbound.telegram.callbacks_handler import router as tg_callbacks_router
        
        # We must include routers in order of priority. 
        # Commands and Onboarding have priority.
        dp.include_router(tg_commands_router)
        dp.include_router(onboarding_router)
        dp.include_router(tg_callbacks_router)

        # The general message handler (pipeline) must be LAST so it doesn't swallow commands
        pipeline_router = Router(name="pipeline")
        @pipeline_router.message()
        async def wrapped_tg_on_message(message: Message, message_processor: MessageProcessingService):
            await tg_on_message(message, message_processor)
        
        dp.include_router(pipeline_router)

        tasks.append(asyncio.create_task(dp.start_polling(tg_bot, handle_signals=False)))

    # Setup Discord
    if dc_token and dc_client and tree:

        @dc_client.event
        async def on_message(message):
            await dc_on_message(message, container.message_processor)

        @dc_client.event
        async def on_ready():
            setup_slash_commands(tree, container.onboarding_completion, container.profile_service)

            # Global Discord Error Handler (Our "Middleware")
            @tree.error
            async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
                if isinstance(error, app_commands.CommandOnCooldown):
                    await interaction.response.send_message(
                        f"⏳ Slow down! Try again in {error.retry_after:.1f}s.", 
                        ephemeral=True
                    )
                else:
                    logger.error(f"Discord Slash Command Error: {error}", exc_info=True)
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            "❌ An unexpected error occurred. Please try again later.", 
                            ephemeral=True
                        )

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
