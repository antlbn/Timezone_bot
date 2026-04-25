import asyncio
import logging
from dataclasses import dataclass
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest

logger = logging.getLogger(__name__)

PRIVATE_CHAT_SENTINEL = "0"

@dataclass(frozen=True)
class OnboardingStartContext:
    target_user_id: int
    source_chat_id: str | None = None

def generate_onboarding_link(bot_username: str, user_id: int, chat_id: str | None) -> str:
    """Generates a deep-link for private onboarding."""
    chat_suffix = f"_{chat_id}" if chat_id and chat_id != "0" else ""
    return f"https://t.me/{bot_username}?start=onboard_{user_id}{chat_suffix}"

def parse_onboarding_payload(payload: str | None) -> OnboardingStartContext | None:
    """Parses the start=onboard_... payload from Telegram."""
    if not payload or not payload.startswith("onboard_"):
        return None
    
    rest = payload[len("onboard_"):]
    if "_" in rest:
        user_part, chat_part = rest.rsplit("_", 1)
    else:
        user_part, chat_part = rest, None

    user_part = user_part.replace("_", "")
    if not user_part.isdigit():
        return None
        
    return OnboardingStartContext(
        target_user_id=int(user_part),
        source_chat_id=chat_part or None,
    )

class DeletionScheduler:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    async def schedule(self, *messages: Message | None, delay: int = 20) -> None:
        """Schedules messages for deletion after a specified delay."""
        if delay <= 0:
            return

        async def deletion_task():
            await asyncio.sleep(delay)
            for message in messages:
                if not message:
                    continue
                try:
                    await message.delete()
                except TelegramAPIError as e:
                    logger.debug(f"Could not delete message {message.message_id}: {e}")

        task = asyncio.create_task(deletion_task())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def cancel_all(self) -> None:
        """Cancels all pending deletion tasks."""
        for t in list(self._tasks):
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

deletion_scheduler = DeletionScheduler()

async def schedule_deletion(*messages: Message | None, delay: int = 20):
    """Schedules messages for deletion after a specified delay.
    
    Safe for use in background tasks. Silently ignores errors.
    """
    await deletion_scheduler.schedule(*messages, delay=delay)

async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    """Safely edits message text, suppressing 'message is not modified' errors."""
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.debug(f"Safe edit failed: {e}")
    except TelegramAPIError as e:
        logger.debug(f"Safe edit failed: {e}")

async def safe_delete_message(message: Message | None):
    """Safely deletes a message, suppressing common errors."""
    if not message:
        return
    try:
        await message.delete()
    except TelegramAPIError as e:
        logger.debug(f"Safe delete failed for message {message.message_id}: {e}")
