import asyncio
import signal
import logging
from aiogram import Bot as TgBot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
import discord
from discord import app_commands

from config import load_config
from container import build_container
from adapters.inbound.telegram.setup import setup_dispatcher
from adapters.inbound.discord.setup import setup_discord

logger = logging.getLogger(__name__)

async def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Timezone Bot (Refactored Composition Root)")

    config = load_config()
    
    if not config.tg_token and not config.dc_token:
        logger.error("No bot tokens found. Exiting.")
        return

    # Initialize Telegram Bot
    tg_bot = None
    tg_username = None
    if config.tg_token:
        tg_bot = TgBot(token=config.tg_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        me = await tg_bot.get_me()
        tg_username = me.username

    # Initialize Discord Client
    dc_client = None
    tree = None
    if config.dc_token:
        intents = discord.Intents.default()
        intents.message_content = True
        dc_client = discord.Client(intents=intents)
        tree = app_commands.CommandTree(dc_client)

    # Build Container (DI & Wiring)
    container = await build_container(
        config=config,
        tg_bot=tg_bot,
        tg_username=tg_username,
        dc_client=dc_client
    )

    tasks = []

    # Setup Telegram
    if tg_bot:
        dp = Dispatcher(storage=MemoryStorage())
        setup_dispatcher(dp, container, config.telegram)
        tasks.append(asyncio.create_task(dp.start_polling(tg_bot, handle_signals=False)))

    # Setup Discord
    if dc_client and tree:
        setup_discord(dc_client, tree, container)
        tasks.append(asyncio.create_task(dc_client.start(config.dc_token)))

    # Lifecycle & Graceful Shutdown
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
            pass 

    if tasks:
        logger.info("Bots started.")
        await stop_event.wait()
        
        # Cleanup
        if tg_bot:
            await dp.stop_polling()
        if dc_client:
            await dc_client.close()
            
        logger.info("Waiting for tasks to exit...")
        await asyncio.gather(*tasks, return_exceptions=True)
    else:
        logger.info("No tasks to run.")

    await container.users_repo.close()
    logger.info("Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted.")
