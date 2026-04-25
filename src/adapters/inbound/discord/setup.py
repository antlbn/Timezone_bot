import logging
import discord
from discord import app_commands
from adapters.inbound.discord.events import on_message as dc_on_message
from adapters.inbound.discord.slash_commands import setup_slash_commands

from container import AppContainer

logger = logging.getLogger(__name__)

def setup_discord(
    client: discord.Client, 
    tree: app_commands.CommandTree, 
    container: AppContainer
) -> None:
    @client.event
    async def on_message(message):
        await dc_on_message(message, container.message_processor)

    @client.event
    async def on_ready():
        setup_slash_commands(tree, container.onboarding_completion, container.profile_service)

        # Global Discord Error Handler
        @tree.error
        async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            if isinstance(error, app_commands.CommandOnCooldown):
                await interaction.response.send_message(
                    f"⏳ Slow down! Try again in {error.retry_after:.1f}s.", 
                    ephemeral=True
                )
            else:
                logger.error(f"Discord Slash Command Error: {error}", exc_info=True)
                if not interaction.response.is_done():
                    from adapters.inbound.discord.ui import texts
                    await interaction.response.send_message(
                        texts.get_unexpected_error_text(), 
                        ephemeral=True
                    )

        try:
            await tree.sync()
            logger.info(f"Discord slash commands synced. Logged in as {client.user}")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
