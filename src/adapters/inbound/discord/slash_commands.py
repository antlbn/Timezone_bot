import discord
from discord import app_commands
import logging
from core.domain.enums import Platform
from core.services.onboarding import OnboardingCompletionUseCase
from core.services.profile import ProfileService
from adapters.inbound.discord import ui

logger = logging.getLogger(__name__)

class TimezoneCommands(app_commands.Group, name="tb"):
    """Group of timezone-related commands for Discord."""
    
    def __init__(
        self, 
        onboarding_completion: OnboardingCompletionUseCase,
        profile_service: ProfileService
    ):
        super().__init__()
        self.onboarding_completion = onboarding_completion
        self.profile_service = profile_service

    @app_commands.command(name="settz", description="Set or change your timezone")
    @app_commands.describe(city="Your city (e.g., Paris, New York)")
    async def settz(self, interaction: discord.Interaction, city: str):
        """Slash command to set user timezone."""
        await interaction.response.defer(ephemeral=True)
        
        city_raw = city.strip()
        res = await self.onboarding_completion.complete(
            user_id=interaction.user.id,
            city_raw=city_raw,
            platform=Platform.DISCORD,
            author_name=interaction.user.display_name
        )
        
        if not res.ok:
            await interaction.followup.send(
                ui.get_city_not_found_text(city_raw), 
                ephemeral=True
            )
            return

        await interaction.followup.send(
            ui.get_completion_text(res.timezone_name, res.city, res.flag),
            ephemeral=True
        )

    @app_commands.command(name="help", description="Show help and commands list")
    async def help(self, interaction: discord.Interaction):
        """Show help text."""
        await interaction.response.send_message(
            ui.get_help_text(),
            ephemeral=True
        )

    @app_commands.command(name="decline", description="Opt out of Timezone Bot features")
    async def decline(self, interaction: discord.Interaction):
        """Opt out of the bot services."""
        await self.onboarding_completion.decline(
            user_id=interaction.user.id,
            platform=Platform.DISCORD,
        )
        await interaction.response.send_message(
            ui.get_decline_confirmation_text(),
            ephemeral=True
        )

    @app_commands.command(name="me", description="Show your current timezone")
    async def me(self, interaction: discord.Interaction):
        """Show current user's profile."""
        user = await self.profile_service.get_user(interaction.user.id, Platform.DISCORD)
        if not user or not user.timezone:
            await interaction.response.send_message(
                ui.get_tz_not_set_text(), 
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            ui.format_user_timezone(user), 
            ephemeral=True
        )

    @app_commands.command(name="members", description="List server members with timezones")
    async def members(self, interaction: discord.Interaction):
        """List all tracked members in the guild."""
        if not interaction.guild:
            await interaction.response.send_message(
                ui.get_server_only_text(), 
                ephemeral=True
            )
            return

        members = await self.profile_service.get_sorted_chat_members(
            str(interaction.guild.id), 
            Platform.DISCORD
        )

        if not members:
            await interaction.response.send_message(
                ui.get_no_members_text(), 
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            ui.format_chat_members(members), 
            ephemeral=True
        )

def setup_slash_commands(
    tree: app_commands.CommandTree, 
    onboarding_completion: OnboardingCompletionUseCase,
    profile_service: ProfileService
):
    """Registers the TimezoneCommands group in the command tree."""
    group = TimezoneCommands(onboarding_completion, profile_service)
    tree.add_command(group)
