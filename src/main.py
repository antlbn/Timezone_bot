"""
Main entry point.
Initializes and runs the Telegram bot.
"""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import get_telegram_token
from src.logger import get_logger
from src.storage import init_db
from src.commands import router

logger = get_logger()


async def main():
    """Main async entry point."""
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Create bot and dispatcher
    bot = Bot(token=get_telegram_token())
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register routers
    dp.include_router(router)
    
    logger.info("Bot starting...")
    
    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
