import discord
from discord import app_commands
from core.domain.enums import Platform
import logging

logger = logging.getLogger(__name__)

def setup_slash_commands(tree: app_commands.CommandTree, container):
    @tree.command(name="tb_settz", description="Set your timezone")
    @app_commands.describe(city="Your city (e.g., Paris, New York)")
    async def tb_settz(interaction: discord.Interaction, city: str):
        # Defer to allow time for API call
        await interaction.response.defer(ephemeral=True)
        res = await container.onboarding_coordinator.complete(
            user_id=interaction.user.id,
            city_raw=city,
            platform=Platform.DISCORD,
        )
        if not res.ok:
            await interaction.followup.send(f"❌ Could not resolve city: {city}", ephemeral=True)
            return

        await interaction.followup.send(
            f"✅ Timezone set to **{res.timezone_name}** ({res.city} {res.flag})", 
            ephemeral=True
        )

    @tree.command(name="tb_help", description="Show help")
    async def tb_help(interaction: discord.Interaction):
        await interaction.response.send_message(
            "I detect time mentions and convert them for your chat members automatically! "
            "Use `/tb_settz` to set your timezone.",
            ephemeral=True
        )

    @tree.command(name="tb_skip", description="Opt out of Timezone Bot features")
    async def tb_skip(interaction: discord.Interaction):
        await container.onboarding_coordinator.decline(
            user_id=interaction.user.id,
            platform=Platform.DISCORD,
        )
        await interaction.response.send_message(
            "Got it! I won't prompt you for your timezone anymore. Use `/tb_settz` if you change your mind.",
            ephemeral=True
        )

    @tree.command(name="tb_me", description="Show your current timezone")
    async def tb_me(interaction: discord.Interaction):
        user = await container.profile_service.get_user(interaction.user.id, Platform.DISCORD)
        if not user or not user.timezone:
            await interaction.response.send_message("Not set. Use `/tb_settz`", ephemeral=True)
            return

        await interaction.response.send_message(
            f"{user.city} {user.flag} ({user.timezone})", ephemeral=True
        )

    @tree.command(name="tb_members", description="List server members with timezones")
    async def tb_members(interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Server only", ephemeral=True)
            return

        members = await container.profile_service.get_sorted_chat_members(str(interaction.guild.id), Platform.DISCORD)

        if not members:
            await interaction.response.send_message("No members yet. Use `/tb_settz`", ephemeral=True)
            return

        lines = ["**Server members:**"]
        for i, m in enumerate(members, 1):
            flag = m.flag or ""
            city = m.city or "Unknown"
            name = f" (@{m.username})" if m.username else ""
            lines.append(f"{i}. {city} {flag}{name}")
            
        # Optional: formatting into embed or simple text
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
