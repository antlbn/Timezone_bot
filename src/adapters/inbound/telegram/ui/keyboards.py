from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from adapters.inbound.telegram.common import PRIVATE_CHAT_SENTINEL
from adapters.inbound.telegram.ui.callbacks import TelegramCallback

def get_settings_keyboard(user_id: int, chat_id: str = PRIVATE_CHAT_SENTINEL, has_timezone: bool = True) -> InlineKeyboardMarkup:
    buttons = []
    if has_timezone:
        buttons.append([
            InlineKeyboardButton(
                text="🔄 Change timezone",
                callback_data=TelegramCallback(action="set_city", user_id=user_id, chat_id=chat_id).pack()
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
            text="📖 Commands List",
            callback_data=TelegramCallback(action="help", user_id=user_id, chat_id=chat_id).pack()
        )
    ])
    
    # Universal decline button
    buttons.append([
        InlineKeyboardButton(
            text="✖️ Stop / Decline bot",
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

def get_onboarding_prompt_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="📍 Set up my timezone",
                url=url,
            )
        ]]
    )

def get_back_to_settings_keyboard(user_id: int, chat_id: str = PRIVATE_CHAT_SENTINEL) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="⬅️ Back to Settings",
            callback_data=TelegramCallback(action="settings", user_id=user_id, chat_id=chat_id).pack()
        )
    ]])
