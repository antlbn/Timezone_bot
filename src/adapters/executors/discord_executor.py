import discord
import logging
from src.adapters.executors.base_executor import BaseCommandExecutor
from src.core.domain.commands import SendReply, ShowOnboarding
from src.adapters.inbound.discord.ui import SetTimezoneView

logger = logging.getLogger(__name__)

class DiscordCommandExecutor(BaseCommandExecutor):
    def __init__(self, pending_port, client: discord.Client):
        super().__init__(pending_port)
        self.client = client
        self.onboarding_service = None

    def set_onboarding_service(self, service):
        self.onboarding_service = service

    async def _get_channel(self, thread_id: str | None) -> discord.abc.Messageable | None:
        if not thread_id:
            return None
        channel = self.client.get_channel(int(thread_id))
        if not channel:
            try:
                channel = await self.client.fetch_channel(int(thread_id))
            except discord.NotFound:
                return None
            except discord.HTTPException as e:
                logger.error(f"Discord HTTP error when fetching channel {thread_id}: {e}")
                return None
            except Exception as e:
                logger.exception(f"Unexpected error fetching channel {thread_id}: {e}")
                return None
        return channel

    async def _handle_send_reply(self, cmd: SendReply) -> None:
        channel = await self._get_channel(cmd.thread_id)
        if not channel:
            return
            
        embed = discord.Embed(description=cmd.text, color=discord.Color.blue())
        await channel.send(embed=embed)

    async def _handle_show_onboarding(self, cmd: ShowOnboarding) -> None:
        channel = await self._get_channel(cmd.thread_id)
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
            view=SetTimezoneView(cmd.user_id, self.onboarding_service),
            delete_after=60
        )
