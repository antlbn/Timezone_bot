from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from adapters.executors.base_executor import BaseCommandExecutor
from core.domain.commands import SendReply, ShowOnboarding
from adapters.inbound.telegram.utils import schedule_deletion

from aiogram import Bot

class TelegramCommandExecutor(BaseCommandExecutor):
    def __init__(self, bot: Bot, bot_username: str):
        super().__init__()
        self.bot = bot
        self._bot_username = bot_username

    async def _handle_send_reply(self, cmd: SendReply) -> None:
        msg = await self.bot.send_message(
            chat_id=cmd.chat_id,
            text=cmd.text,
            message_thread_id=int(cmd.thread_id) if cmd.thread_id else None
        )
        
        # Auto-delete conversion results in groups after 20s
        if int(cmd.chat_id) < 0:
            await schedule_deletion(msg, delay=20)

    async def _handle_show_onboarding(self, cmd: ShowOnboarding) -> None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="⚙️ Set my city",
                    url=f"https://t.me/{self._bot_username}?start=onboard_{cmd.user_id}_{cmd.chat_id}",
                )
            ]]
        )
        msg = await self.bot.send_message(
            chat_id=cmd.chat_id,
            text=f"👋 <b>{cmd.author_name}</b>, to convert your time correctly, "
                 f"please specify your city. ",
            reply_markup=keyboard,
            message_thread_id=int(cmd.thread_id) if cmd.thread_id else None
        )
        
        # Auto-delete setup prompt in groups after 20s
        if int(cmd.chat_id) < 0:
            await schedule_deletion(msg, delay=20)
