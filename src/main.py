import asyncio
import os
import signal
import logging
from dataclasses import dataclass
from pathlib import Path
from aiogram import Bot as TgBot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import discord
import yaml
from discord import app_commands
from dotenv import load_dotenv

from src.adapters.outbound.sqlite_storage import SQLiteStorage
from src.adapters.outbound.openai_detector import OpenAIDetector
from src.adapters.outbound.nominatim_geo import NominatimGeo
from src.adapters.outbound.memory_pending import MemoryPending
from src.adapters.executors.telegram_executor import TelegramCommandExecutor
from src.adapters.executors.discord_executor import DiscordCommandExecutor
from src.core.pipeline.pipeline import Pipeline
from src.core.domain.value_objects import BotSettings
from src.core.domain.enums import ResponseStyle
from src.ports.storage import StoragePort
from src.ports.geocoding import GeoPort

@dataclass
class AppContainer:
    storage: StoragePort
    pipeline: Pipeline
    tg_executor: TelegramCommandExecutor
    dc_executor: DiscordCommandExecutor
    geocoder: GeoPort

logger = logging.getLogger(__name__)



async def main():
    # Deferred imports to avoid circular dependency since AppContainer is now in main.py
    from src.adapters.inbound.telegram.handlers import on_message as tg_on_message
    from src.adapters.inbound.discord.events import on_message as dc_on_message
    from src.adapters.inbound.discord.slash_commands import setup_slash_commands
    from src.core.pipeline.stages import GuardStage, AgingStage, DetectionStage, ResolveStage, FormatStage, CommandFactoryStage

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
    pending = MemoryPending()

    # Load configuration
    config_path = Path("configuration.yaml")
    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)

    bot_config = config_data.get("bot", {})
    response_style_str = bot_config.get("response_style", "block")
    
    # Map string to Enum
    if response_style_str.lower() == "inline_sentence":
        style = ResponseStyle.INLINE
    else:
        style = ResponseStyle.BLOCK

    settings = BotSettings(
        show_usernames=bot_config.get("show_usernames", False),
        show_event_title=bot_config.get("show_event_title", True),
        response_style=style
    )

    pipeline = Pipeline([
        GuardStage(),
        AgingStage(max_age_seconds=config_data.get("event_detection", {}).get("max_message_age_seconds", 120)),
        DetectionStage(detector),
        ResolveStage(storage),
        FormatStage(settings),
        CommandFactoryStage()
    ])

    tg_executor = TelegramCommandExecutor(pending_port=pending)
    dc_executor = DiscordCommandExecutor(pending_port=pending)

    container = AppContainer(storage, pipeline, tg_executor, dc_executor, geocoder)

    tasks = []

    # Setup Telegram
    if tg_token:
        tg_bot = TgBot(token=tg_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()

        @dp.message()
        async def wrapped_tg_on_message(message):
            await tg_on_message(message, container)

        tasks.append(asyncio.create_task(dp.start_polling(tg_bot, handle_signals=False)))

    # Setup Discord
    if dc_token:
        intents = discord.Intents.default()
        intents.message_content = True
        dc_client = discord.Client(intents=intents)
        tree = app_commands.CommandTree(dc_client)

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
