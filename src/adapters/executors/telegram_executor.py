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
                InlineKeyboardButton(
                    text="⚙️ Указать город",
                    url="https://t.me/TimezoneWizard?start=onboard",
                )
            ]]
        )
        await context.message.answer(
            f"👋 <b>{cmd.author_name}</b>, чтобы правильно конвертировать время — "
            f"укажи свой город. Это займёт 10 секунд 🙂",
            reply_markup=keyboard,
        )
