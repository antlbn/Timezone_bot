import asyncio
import logging
from dataclasses import dataclass
from aiogram.types import Message
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

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

async def schedule_deletion(message: Message, delay: int = 20):
    """Schedules a message for deletion after a specified delay.
    
    Safe for use in background tasks. Silently ignores errors.
    """
    if not message or delay <= 0:
        return

    async def _delete():
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except TelegramAPIError:
            pass
        except Exception as e:
            logger.debug(f"Failed to delete message {message.message_id}: {e}")

    asyncio.create_task(_delete())
