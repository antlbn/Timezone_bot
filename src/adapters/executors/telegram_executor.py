from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from adapters.executors.base_executor import BaseCommandExecutor
from core.domain.commands import SendReply, ShowOnboarding

from aiogram import Bot

class TelegramCommandExecutor(BaseCommandExecutor):
    def __init__(self, onboarding_pending_port, onboarding_chillout_state_port, bot: Bot):
        super().__init__(onboarding_pending_port, onboarding_chillout_state_port)
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
