from aiogram.filters.callback_data import CallbackData
from adapters.inbound.telegram.common import PRIVATE_CHAT_SENTINEL

class TelegramCallback(CallbackData, prefix="tg"):
    action: str  # "set_city" | "decline" | "remove" | "settings" | "privacy" | "help"
    user_id: int
    chat_id: str = PRIVATE_CHAT_SENTINEL
