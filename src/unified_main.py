"""
Unified Bot Launcher - runs both Telegram and Discord bots.

Usage:
    uv run python -m src.unified_main
"""
import os
import asyncio

from dotenv import load_dotenv

from src.config import get_config
from src.logger import get_logger, setup_logging
from src.storage import storage

logger = get_logger()


async def start_telegram():
    """Start Telegram bot if enabled and token present."""
    config = get_config()
    
    if not config.get("telegram", {}).get("enabled", True):
        logger.info("Telegram bot disabled in config")
        return None
    
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.warning("TELEGRAM_TOKEN not set, skipping Telegram bot")
        return None
    
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from src.commands import router, PassiveCollectionMiddleware
    
    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(PassiveCollectionMiddleware())
    dp.include_router(router)
    
    logger.info("Starting Telegram bot...")
    
    # Return coroutine for concurrent execution
    return dp.start_polling(bot)


async def start_discord():
    """Start Discord bot if enabled and token present."""
    config = get_config()
    
    if not config.get("discord", {}).get("enabled", False):
        logger.info("Discord bot disabled in config")
        return None
    
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.warning("DISCORD_TOKEN not set, skipping Discord bot")
        return None
    
    from src.discord import bot
    import src.discord.commands  # noqa: F401
    import src.discord.events    # noqa: F401
    
    logger.info("Starting Discord bot...")
    
    return bot.start(token)


async def main():
    """Run enabled bots concurrently."""
    load_dotenv()
    setup_logging()
    
    # Initialize storage once
    await storage.init()
    logger.info("Storage initialized")
    
    # Get bot coroutines
    telegram_task = await start_telegram()
    discord_task = await start_discord()
    
    tasks = [t for t in [telegram_task, discord_task] if t is not None]
    
    if not tasks:
        logger.error("No bots enabled or no tokens provided!")
        return
    
    logger.info(f"Running {len(tasks)} bot(s)...")
    
    # Run all bots concurrently
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
