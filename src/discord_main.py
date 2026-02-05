"""
Discord Bot Entry Point.

Usage:
    uv run python -m src.discord_main
"""
import os
import asyncio

from dotenv import load_dotenv

from src.config import get_config
from src.logger import get_logger, setup_logging
from src.storage import storage

logger = get_logger()


async def main():
    """Start the Discord bot."""
    load_dotenv()
    setup_logging()
    
    config = get_config()
    discord_config = config.get("discord", {})
    
    # Check if Discord is enabled
    if not discord_config.get("enabled", False):
        logger.info("Discord bot disabled in config")
        return
    
    # Check for token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.warning("DISCORD_TOKEN not set, skipping Discord bot")
        return
    
    # Initialize storage
    await storage.init()
    logger.info("Storage initialized")
    
    # Import bot and register commands/events
    from src.discord import bot
    import src.discord.commands  # noqa: F401 - registers commands
    import src.discord.events    # noqa: F401 - registers events
    
    logger.info("Starting Discord bot...")
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
