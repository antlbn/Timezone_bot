import discord
import logging
from collections.abc import Callable
from adapters.executors.base_executor import BaseCommandExecutor
from core.domain.commands import SendReply, ShowOnboarding

logger = logging.getLogger(__name__)

class DiscordCommandExecutor(BaseCommandExecutor):
    def __init__(
        self,
        client: discord.Client,
        onboarding_view_factory: Callable[[int], discord.ui.View],
    ):
        super().__init__()
        self.client = client
        self._onboarding_view_factory = onboarding_view_factory

    async def _get_channel(self, thread_id: str | None, chat_id: str) -> discord.abc.Messageable | None:
        target_id = thread_id or chat_id
        if not target_id:
            return None
            
        channel_id = int(target_id)
        channel = self.client.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.client.fetch_channel(channel_id)
            except discord.NotFound:
                return None
            except discord.HTTPException as e:
                logger.error(f"Discord HTTP error when fetching channel {channel_id}: {e}")
                return None
            except Exception as e:
                logger.exception(f"Unexpected error fetching channel {channel_id}: {e}")
                return None
        return channel

    async def _handle_send_reply(self, cmd: SendReply) -> None:
        channel = await self._get_channel(cmd.thread_id, cmd.chat_id)
        if not channel:
            return
            
        embed = discord.Embed(description=cmd.text, color=discord.Color.blue())
        await channel.send(embed=embed)

    async def _handle_show_onboarding(self, cmd: ShowOnboarding) -> None:
        channel = await self._get_channel(cmd.thread_id, cmd.chat_id)
        if not channel:
            return
            
        embed = discord.Embed(
            title=f"👋 Welcome to Timezone Bot, {cmd.author_name}!",
            description="I've detected a time mention, but I don't know your timezone yet.\n\n"
                        "Tap the button below to quickly set it up! (Only you will see the next steps)",
            color=discord.Color.gold(),
        )
        await channel.send(
            content=f"<@{cmd.user_id}>",
            embed=embed,
            view=self._onboarding_view_factory(cmd.user_id),
            delete_after=60
        )
