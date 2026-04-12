import discord
from discord import app_commands
from src.core.domain.enums import Platform
import logging

logger = logging.getLogger(__name__)

def setup_slash_commands(tree: app_commands.CommandTree, container):
    @tree.command(name="tb_settz", description="Set your timezone")
    @app_commands.describe(city="Your city (e.g., Paris, New York)")
    async def tb_settz(interaction: discord.Interaction, city: str):
        # Resolve city using GeoPort
        location = await container.geocoder.resolve_city(city)
        if not location:
            await interaction.response.send_message(f"❌ Could not resolve city: {city}", ephemeral=True)
            return
            
        await container.storage.set_user(
            user_id=interaction.user.id,
            platform=Platform.DISCORD,
            timezone=location.timezone,
            city=location.city,
            flag=location.flag
        )
        
        await interaction.response.send_message(
            f"✅ Timezone set to **{location.timezone}** ({location.city} {location.flag})", 
            ephemeral=True
        )

    @tree.command(name="tb_help", description="Show help")
    async def tb_help(interaction: discord.Interaction):
        await interaction.response.send_message(
            "I detect time mentions and convert them for your chat members automatically! "
            "Use `/tb_settz` to set your timezone.",
            ephemeral=True
        )
