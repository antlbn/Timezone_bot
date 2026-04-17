import discord
from src.adapters.executors.base import BaseCommandExecutor
from src.core.domain.commands import SendReply, ShowOnboarding
from src.adapters.inbound.discord.ui import SetTimezoneView

class DiscordCommandExecutor(BaseCommandExecutor):
    def __init__(self, pending_port, client: discord.Client):
        super().__init__(pending_port)
        self.client = client

    async def _get_channel(self, thread_id: str | None) -> discord.abc.Messageable | None:
        if not thread_id:
            return None
        channel = self.client.get_channel(int(thread_id))
        if not channel:
            try:
                channel = await self.client.fetch_channel(int(thread_id))
            except Exception:
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
            view=SetTimezoneView(cmd.user_id),
            delete_after=60
        )
