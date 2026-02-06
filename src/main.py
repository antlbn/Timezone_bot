"""
Main entry point.
Initializes and runs the Telegram bot.
"""
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import get_telegram_token
from src.logger import get_logger
from src.storage import storage
from src.commands import router, PassiveCollectionMiddleware

logger = get_logger()



async def on_startup(bot: Bot):
    """Startup hook."""
    logger.info("Bot starting...")
    
    # Initialize DB
    await storage.init()
    logger.info("Database initialized")
    



async def main():
    """Main async entry point."""
    # Check for token - if not present, skip gracefully
    token = get_telegram_token()
    if not token:
        logger.warning("TELEGRAM_TOKEN not set, skipping Telegram bot")
        return
    
    # Create bot and dispatcher
    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register startup hook
    dp.startup.register(on_startup)
    
    # Register middleware
    dp.message.middleware(PassiveCollectionMiddleware())
    
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

