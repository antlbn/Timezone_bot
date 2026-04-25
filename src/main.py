import asyncio
import signal
import logging
from collections.abc import Coroutine

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


def _create_task(
    tasks: dict[str, asyncio.Task[object]],
    name: str,
    coroutine: Coroutine[object, object, object],
) -> None:
    tasks[name] = asyncio.create_task(coroutine, name=name)


async def _wait_for_shutdown(tasks: dict[str, asyncio.Task[object]], stop_event: asyncio.Event) -> None:
    stop_waiter = asyncio.create_task(stop_event.wait(), name="shutdown-waiter")
    try:
        done, pending = await asyncio.wait(
            [*tasks.values(), stop_waiter],
            return_when=asyncio.FIRST_COMPLETED,
        )

        if stop_waiter in done:
            return

        for finished in done:
            if finished is stop_waiter:
                continue
            try:
                finished.result()
            except Exception:
                logger.exception("Background task %s exited unexpectedly.", finished.get_name())
            else:
                logger.warning("Background task %s exited unexpectedly without an error.", finished.get_name())
        stop_event.set()

        for leftover in pending:
            if leftover is stop_waiter:
                continue
            logger.info("Task %s is still running and will be stopped.", leftover.get_name())
    finally:
        stop_waiter.cancel()
        await asyncio.gather(stop_waiter, return_exceptions=True)


async def main() -> None:
    config = load_config()
    logging.basicConfig(level=getattr(logging, config.logging.level, logging.INFO))
    logger.info("Starting Timezone Bot (Refactored Composition Root)")
    
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

    tasks: dict[str, asyncio.Task[object]] = {}
    dp: Dispatcher | None = None

    # Setup Telegram
    if tg_bot:
        dp = Dispatcher(storage=MemoryStorage())
        setup_dispatcher(dp, container, config.telegram)
        _create_task(tasks, "telegram-polling", dp.start_polling(tg_bot, handle_signals=False))

    # Setup Discord
    if dc_client and tree:
        setup_discord(dc_client, tree, container)
        dc_token = config.dc_token
        assert dc_token is not None
        _create_task(tasks, "discord-client", dc_client.start(dc_token))

    # Lifecycle & Graceful Shutdown
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
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
        await _wait_for_shutdown(tasks, stop_event)

        if tg_bot and dp is not None:
            await dp.stop_polling()
        if dc_client:
            await dc_client.close()

        logger.info("Waiting for tasks to exit...")
        await asyncio.gather(*tasks.values(), return_exceptions=True)
    else:
        logger.info("No tasks to run.")

    logger.info("Cancelling background deletion tasks...")
    from adapters.inbound.telegram.common import deletion_scheduler
    await deletion_scheduler.cancel_all()

    await container.storage.close()
    logger.info("Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted.")
