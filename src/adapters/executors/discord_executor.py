import discord
from src.adapters.executors.base import BaseCommandExecutor
from src.core.domain.commands import SendReply, ShowOnboarding
from src.adapters.inbound.discord.ui import SetTimezoneView

class DiscordCtx:
    def __init__(self, message: discord.Message):
        self.message = message

class DiscordCommandExecutor(BaseCommandExecutor):
    async def _handle_send_reply(self, cmd: SendReply, context: DiscordCtx) -> None:
        embed = discord.Embed(description=cmd.text, color=discord.Color.blue())
        await context.message.channel.send(embed=embed)

    async def _handle_show_onboarding(self, cmd: ShowOnboarding, context: DiscordCtx) -> None:
        embed = discord.Embed(
            title=f"👋 Welcome to Timezone Bot, {cmd.author_name}!",
            description="I've detected a time mention, but I don't know your timezone yet.\n\n"
                        "Tap the button below to quickly set it up! (Only you will see the next steps)",
            color=discord.Color.gold(),
        )
        await context.message.reply(
            embed=embed,
            view=SetTimezoneView(cmd.user_id),
            mention_author=True,
            delete_after=60
        )
