import asyncio
import os
import logging
from pathlib import Path
from aiogram import Bot as TgBot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import discord
from discord import app_commands
from dotenv import load_dotenv

from src.adapters.outbound.sqlite_storage import SQLiteStorage
from src.adapters.outbound.openai_detector import OpenAIDetector
from src.adapters.outbound.nominatim_geo import NominatimGeo
from src.adapters.outbound.memory_pending import MemoryPending
from src.adapters.executors.telegram_executor import TelegramCommandExecutor
from src.adapters.executors.discord_executor import DiscordCommandExecutor
from src.core.pipeline.pipeline import Pipeline
from src.core.pipeline.stages import GuardStage, AgingStage, DetectionStage, ResolveStage, FormatStage
from src.adapters.inbound.telegram.handlers import on_message as tg_on_message
from src.adapters.inbound.discord.events import on_message as dc_on_message
from src.adapters.inbound.discord.slash_commands import setup_slash_commands

logger = logging.getLogger(__name__)

class AppContainer:
    def __init__(self, storage, pipeline, tg_executor, dc_executor, geocoder):
        self.storage = storage
        self.pipeline = pipeline
        self.tg_executor = tg_executor
        self.dc_executor = dc_executor
        self.geocoder = geocoder

async def main():
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

    pipeline = Pipeline([
        GuardStage(),
        AgingStage(max_age_seconds=120),
        DetectionStage(detector),
        ResolveStage(storage),
        FormatStage(storage)
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

        tasks.append(asyncio.create_task(dp.start_polling(tg_bot)))

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

    try:
        if tasks:
            logger.info("Bots started polling.")
            await asyncio.gather(*tasks)
        else:
            logger.info("No tasks to run.")
    finally:
        await storage.close()

if __name__ == "__main__":
    asyncio.run(main())
