from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

class TelegramCallback(CallbackData, prefix="tg"):
    action: str  # "set_city" | "decline" | "remove" | "settings" | "privacy" | "help"
    user_id: int
    chat_id: str = "0"

def get_help_text(chat_type: str) -> str:
    # Consistency: tb_help and commands tab show the same thing now
    return (
        "<b>Timezone Bot Help</b>\n\n"
        "Personal commands:\n"
        "• /tb_me — show your current timezone\n"
        "• /tb_settz — set or change your timezone\n"
        "• /tb_decline — stop the bot and ignore me\n\n"
        "Group commands:\n"
        "• /tb_members — list tracked members in the current chat\n\n"
        "Mention a time in a group chat and I'll convert it for known members automatically."
    )

def get_settings_keyboard(user_id: int, chat_id: str = "0", has_timezone: bool = True) -> InlineKeyboardMarkup:
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
    
    if has_timezone:
        buttons.append([
            InlineKeyboardButton(
                text="🗑️ Remove timezone",
                callback_data=TelegramCallback(action="remove", user_id=user_id, chat_id=chat_id).pack()
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

def get_back_to_settings_keyboard(user_id: int, chat_id: str = "0") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="⬅️ Back to Settings",
            callback_data=TelegramCallback(action="settings", user_id=user_id, chat_id=chat_id).pack()
        )
    ]])
