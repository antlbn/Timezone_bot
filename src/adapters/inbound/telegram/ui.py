from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

class TelegramCallback(CallbackData, prefix="tg"):
    action: str  # "set_city" | "decline" | "remove" | "settings" | "privacy"
    user_id: int
    chat_id: str = "0"

def get_settings_keyboard(user_id: int, chat_id: str = "0", has_timezone: bool = True) -> InlineKeyboardMarkup:
    buttons = []
    if has_timezone:
        buttons.append([
            InlineKeyboardButton(
                text="🔄 Change timezone",
                callback_data=TelegramCallback(action="set_city", user_id=user_id, chat_id=chat_id).pack()
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                text="🗑️ Remove timezone",
                callback_data=TelegramCallback(action="remove", user_id=user_id, chat_id=chat_id).pack()
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="📍 Set my city",
                callback_data=TelegramCallback(action="set_city", user_id=user_id, chat_id=chat_id).pack()
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                text="✖️ No thanks",
                callback_data=TelegramCallback(action="decline", user_id=user_id, chat_id=chat_id).pack()
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="🔒 Data Privacy",
            callback_data=TelegramCallback(action="privacy", user_id=user_id).pack()
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
