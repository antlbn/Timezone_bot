"""
Discord Bot Module - Bot instance and intents setup.
"""
import discord
from discord import app_commands

from src.logger import get_logger

logger = get_logger()

# Intents: we need message content and guild members
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class TimezoneBot(discord.Client):
    """Discord client with slash command support."""
    
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
    
    async def setup_hook(self):
        """Called when bot is ready - sync commands."""
        await self.tree.sync()
        logger.info("Discord slash commands synced")
    
    async def on_ready(self):
        """Log when bot is connected."""
        logger.info(f"Discord bot connected as {self.user}")


# Singleton bot instance
bot = TimezoneBot()
