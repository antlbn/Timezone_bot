from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from src.adapters.executors.base import BaseCommandExecutor
from src.core.domain.commands import SendReply, ShowOnboarding

class TelegramCtx:
    def __init__(self, message: Message):
        self.message = message

class TelegramCommandExecutor(BaseCommandExecutor):
    async def _handle_send_reply(self, cmd: SendReply, context: TelegramCtx) -> None:
        await context.message.answer(cmd.text)

    async def _handle_show_onboarding(self, cmd: ShowOnboarding, context: TelegramCtx) -> None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Set Timezone", url="https://t.me/your_bot_name?start=set_tz")
            ]]
        )
        await context.message.answer(
            f"Hello {cmd.author_name}! To convert time properly, please set your timezone.",
            reply_markup=keyboard
        )
