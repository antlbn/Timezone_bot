"""
Main entry point.
Initializes and runs the Telegram bot.
"""
import asyncio
import subprocess
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import get_telegram_token
from src.logger import get_logger
from src.storage import init_db
from src.commands import router, PassiveCollectionMiddleware

logger = get_logger()

# Update interval: 7 days in seconds
TZDATA_UPDATE_INTERVAL = 7 * 24 * 60 * 60


def update_tzdata():
    """Update tzdata package to ensure timezone data is current."""
    try:
        result = subprocess.run(
            ["uv", "pip", "install", "--upgrade", "tzdata"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            logger.info("tzdata updated successfully")
        else:
            logger.warning(f"tzdata update failed: {result.stderr}")
    except Exception as e:
        logger.warning(f"Could not update tzdata: {e}")


async def tzdata_update_loop():
    """Background task: update tzdata weekly."""
    while True:
        await asyncio.sleep(TZDATA_UPDATE_INTERVAL)
        update_tzdata()


async def on_startup(bot: Bot):
    """Startup hook."""
    logger.info("Bot starting...")
    
    # Initialize DB
    await storage.init()
    logger.info("Database initialized")
    
    # Update tzdata
    logger.info("Checking tzdata version...")
    update_tzdata()


async def main():
    """Main async entry point."""
    # Create bot and dispatcher
    bot = Bot(token=get_telegram_token())
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register startup hook
    dp.startup.register(on_startup)
    
    # Register middleware
    dp.message.middleware(PassiveCollectionMiddleware())
    
    # Register routers
    dp.include_router(router)
    
    # Start background tzdata updater
    asyncio.create_task(tzdata_update_loop())
    
    logger.info("Bot starting...")
    
    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

