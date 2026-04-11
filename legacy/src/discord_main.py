"""
Discord Bot Entry Point.

Usage:
    uv run python -m src.discord_main
"""

import os
import asyncio

from dotenv import load_dotenv

from src.logger import get_logger, setup_logging
from src.storage import storage

logger = get_logger()


async def main():
    """Start the Discord bot."""
    load_dotenv()
    setup_logging()
    logger.warning("❤️❤️❤️ DISCORD BOT STARTING FROM LIVE SOURCE ❤️❤️❤️")

    # Check for token - if present, start bot
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.warning("DISCORD_TOKEN not set, skipping Discord bot")
        return

    # Initialize storage
    await storage.init()
    logger.info("Storage initialized")

    # Import bot and register commands/events
    # Importing these modules triggers @bot.tree.command and @bot.event decorators
    from src.discord import bot  # noqa: F401
    import src.discord.commands  # noqa: F401
    import src.discord.events  # noqa: F401
    from src.discord.tasks import start_tasks

    start_tasks()
    logger.info("Discord background tasks initialized")

    logger.info("Starting Discord bot...")
    try:
        await bot.start(token)
    finally:
        logger.info("Closing storage for Discord bot...")
        await storage.close()
        logger.info("Discord bot shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
