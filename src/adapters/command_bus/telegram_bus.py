from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.adapters.command_bus.base_bus import BaseCommandBus
from src.core.domain.commands import SendReply, ShowOnboarding

from aiogram import Bot

class TelegramCommandBus(BaseCommandBus):
    def __init__(self, pending_port, bot: Bot):
        super().__init__(pending_port)
        self.bot = bot

    async def _handle_send_reply(self, cmd: SendReply) -> None:
        await self.bot.send_message(
            chat_id=cmd.chat_id,
            text=cmd.text,
            message_thread_id=int(cmd.thread_id) if cmd.thread_id else None
        )

    async def _handle_show_onboarding(self, cmd: ShowOnboarding) -> None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="⚙️ Указать город",
                    url="https://t.me/TimezoneWizard?start=onboard",
                )
            ]]
        )
        await self.bot.send_message(
            chat_id=cmd.chat_id,
            text=f"👋 <b>{cmd.author_name}</b>, чтобы правильно конвертировать время — "
                 f"укажи свой город. Это займёт 10 секунд 🙂",
            reply_markup=keyboard,
            message_thread_id=int(cmd.thread_id) if cmd.thread_id else None
        )
