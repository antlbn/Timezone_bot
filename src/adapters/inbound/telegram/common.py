import asyncio
import logging
from dataclasses import dataclass
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
import contextlib

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
    
    parts = payload.split("_")
    if len(parts) not in (2, 3):
        return None
    
    raw_user_id = parts[1]
    if not raw_user_id.isdigit():
        return None
    
    source_chat_id = None
    if len(parts) == 3:
        source_chat_id = parts[2]
        if not source_chat_id or source_chat_id == "-":
            return None
            
    return OnboardingStartContext(
        target_user_id=int(raw_user_id),
        source_chat_id=source_chat_id,
    )

async def schedule_deletion(*messages: Message | None, delay: int = 20):
    """Schedules messages for deletion after a specified delay.
    
    Safe for use in background tasks. Silently ignores errors.
    """
    if delay <= 0:
        return

    async def _delete():
        await asyncio.sleep(delay)
        for message in messages:
            if not message:
                continue
            try:
                await message.delete()
            except TelegramAPIError as e:
                logger.debug(f"Could not delete message {message.message_id}: {e}")

    asyncio.create_task(_delete())

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
