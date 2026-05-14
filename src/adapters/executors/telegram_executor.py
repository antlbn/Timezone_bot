from adapters.executors.base_executor import BaseCommandExecutor
from core.domain.commands import SendReply, ShowOnboarding
from adapters.inbound.telegram.common import generate_onboarding_link, DeletionScheduler
from adapters.inbound.telegram.config import TelegramConfig
from adapters.inbound.telegram import ui

from aiogram import Bot

class TelegramCommandExecutor(BaseCommandExecutor):
    def __init__(self, bot: Bot, bot_username: str, config: TelegramConfig, deletion_scheduler: DeletionScheduler):
        super().__init__()
        self.bot = bot
        self._bot_username = bot_username
        self._config = config
        self._deletion_scheduler = deletion_scheduler

    async def _handle_send_reply(self, cmd: SendReply) -> None:
        msg = await self.bot.send_message(
            chat_id=cmd.chat_id,
            text=cmd.text,
            message_thread_id=int(cmd.thread_id) if cmd.thread_id else None
        )
        
        # Policy: stay in groups, delete in private
        is_group = int(cmd.chat_id) < 0
        if not is_group:
            await self._deletion_scheduler.schedule(msg, delay=self._config.delete_delay)

    async def _handle_show_onboarding(self, cmd: ShowOnboarding) -> None:
        url = generate_onboarding_link(self._bot_username, cmd.user_id, cmd.chat_id)
        
        msg = await self.bot.send_message(
            chat_id=cmd.chat_id,
            text=ui.get_onboarding_prompt_text(cmd.author_name),
            reply_markup=ui.get_onboarding_prompt_keyboard(url),
            message_thread_id=int(cmd.thread_id) if cmd.thread_id else None
        )
        
        # Policy: always delete (onboarding is setup/settings)
        await self._deletion_scheduler.schedule(msg, delay=self._config.delete_delay)
