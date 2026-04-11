import asyncio
import os
import logging
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from src.adapters.outbound.sqlite_storage import SQLiteStorage
from src.adapters.outbound.openai_detector import OpenAIDetector
from src.adapters.outbound.nominatim_geo import NominatimGeo
from src.adapters.outbound.memory_pending import MemoryPending
from src.adapters.executors.telegram_executor import TelegramCommandExecutor
from src.core.pipeline.pipeline import Pipeline
from src.core.pipeline.stages import GuardStage, AgingStage, DetectionStage, ResolveStage, FormatStage
from src.adapters.inbound.telegram.handlers import on_message

logger = logging.getLogger(__name__)

class AppContainer:
    def __init__(self, storage, pipeline, tg_executor):
        self.storage = storage
        self.pipeline = pipeline
        self.tg_executor = tg_executor

async def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Timezone Bot with new Hexagonal Architecture (M2)")

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not tg_token:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return

    bot = Bot(token=tg_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Create Outbound Adapters
    db_path = Path("data/bot.db")
    storage = SQLiteStorage(db_path)
    # Ensure init_db is complete
    await storage._get_conn() 

    detector = OpenAIDetector()
    geocoder = NominatimGeo()
    pending = MemoryPending()

    # Create Core Pipeline
    pipeline = Pipeline([
        GuardStage(),
        AgingStage(max_age_seconds=120),
        DetectionStage(detector),
        ResolveStage(storage),
        FormatStage(storage)
    ])

    # Create Executors
    tg_executor = TelegramCommandExecutor(pending_port=pending)

    # Composition Root Container
    container = AppContainer(storage, pipeline, tg_executor)

    # Register handlers
    @dp.message()
    async def wrapped_on_message(message):
        await on_message(message, container)

    try:
        logger.info("Bot started polling.")
        await dp.start_polling(bot)
    finally:
        await storage.close()

if __name__ == "__main__":
    asyncio.run(main())
