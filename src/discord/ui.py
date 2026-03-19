"""
Discord UI Components (Modals and Views).
"""

import discord
from discord import ui
from typing import Optional, List, Dict, Any, Union
from src.logger import get_logger

logger = get_logger()


class TimezoneModal(ui.Modal, title="Set Your Timezone"):
    """Modal for entering city name."""

    city = ui.TextInput(
        label="Your City",
        placeholder="e.g. Paris 🇫🇷 | Paris, Texas 🇺🇸 | London 🇬🇧",
        min_length=2,
        max_length=100,
        required=True,
    )

    def __init__(self, origin_interaction: Optional[discord.Interaction] = None):
        super().__init__()
        self.origin_interaction = origin_interaction

    async def on_submit(self, interaction: discord.Interaction):
        # Local import to avoid circular dependency
        from src.discord.commands import handle_settz

        await handle_settz(interaction, self.city.value, origin_interaction=self.origin_interaction)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        embed = discord.Embed(
            title="⚠️ Error",
            description="Oops! Something went wrong while processing your request.",
            color=discord.Color.red(),
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.error(f"Modal error: {error}", exc_info=error)


class TimeInputModal(ui.Modal, title="Enter Time Manually"):
    """Modal for entering time directly."""

    time_str = ui.TextInput(
        label="Current Time",
        placeholder="e.g. 15:30",
        min_length=4,
        max_length=5,
        required=True,
    )

    def __init__(self, origin_interaction: Optional[discord.Interaction] = None):
        super().__init__()
        self.origin_interaction = origin_interaction

    async def on_submit(self, interaction: discord.Interaction):
        # Local import to avoid circular dependency
        from src.discord.commands import handle_manual_time

        await handle_manual_time(interaction, self.time_str.value, origin_interaction=self.origin_interaction)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        embed = discord.Embed(
            title="⚠️ Error",
            description="Oops! Something went wrong while processing your manual time input.",
            color=discord.Color.red(),
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.error(f"TimeModal error: {error}", exc_info=error)


def get_welcome_embed(user_name: str) -> discord.Embed:
    """Helper to generate the Telegram-parity welcome message."""
    embed = discord.Embed(
        title=f"👋 Hi {user_name}!",
        description=(
            f"🤖 **What I am**\n"
            f"I'm a bot that converts times for chat members across "
            f"different cities and time zones. When someone mentions a time, "
            f"I show what it is for everyone else.\n"
            f"\n"
            f"💬 **How to use me**\n"
            f"You don't need to do anything special — just chat as usual. "
            f"I'll detect when someone talks about events and times, and "
            f"reply with the converted time automatically.\n"
            f"\n"
            f"⚙️ **Set up your location**\n"
            f"To get started, I need to know your city. You can always change this "
            f"later or remove your data by coming back here or using `/tb_settz` in any chat.\n"
            f"\n"
            f"Ready? Tap **📍 Set City** below 👇"
        ),
        color=discord.Color.blue(),
    )
    return embed


class SetTimezoneView(ui.View):
    """Initial invitation in group - single button to start setup."""

    def __init__(self, target_user_id: int):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @ui.button(
        label="Start Setup",
        style=discord.ButtonStyle.primary,
        custom_id="settz_button",
    )
    async def start_setup(self, interaction: discord.Interaction, button: ui.Button):
        # Respond with the ephemeral menu
        user_name = interaction.user.display_name
        embed = get_welcome_embed(user_name)
        
        await interaction.response.send_message(
            embed=embed,
            view=OnboardingMenuView(self.target_user_id, interaction.guild_id),
            ephemeral=True
        )
        
        # Try to delete the public invite message to reduce clutter
        try:
            if interaction.message:
                await interaction.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete invite message: {e}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            embed = discord.Embed(
                description="❌ This button is not for you!",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True


class OnboardingMenuView(ui.View):
    """Ephemeral menu with 4 main onboarding options."""

    def __init__(self, target_user_id: int, guild_id: Optional[int]):
        super().__init__(timeout=300)
        self.target_user_id = target_user_id
        self.guild_id = guild_id

    @ui.button(label="📍 Set City", style=discord.ButtonStyle.primary)
    async def set_city(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TimezoneModal(origin_interaction=interaction))

    @ui.button(label="👥 Members", style=discord.ButtonStyle.secondary)
    async def show_members(self, interaction: discord.Interaction, button: ui.Button):
        from src.storage import storage
        if not self.guild_id:
            return await interaction.response.send_message("This command only works in servers.", ephemeral=True)
            
        members = await storage.get_chat_members(self.guild_id, platform="discord")
        if not members:
            description = "No members are currently being tracked in this server."
        else:
            description = "\n".join([
                f"• **{m.get('username') or 'User'}**: {m.get('city')} {m.get('flag', '')} (`{m.get('timezone')}`)"
                for m in members
            ])

        embed = discord.Embed(
            title=f"👥 Tracked Members",
            description=description,
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: ui.Button):
        from src.storage import storage
        from src.storage.user_cache import invalidate_user_cache
        from src.storage.pending import get_and_delete_pending_messages

        # Save declined status
        await storage.set_user(
            user_id=interaction.user.id,
            platform="discord",
            city=None,
            timezone=None,
            onboarding_declined=True
        )
        invalidate_user_cache(interaction.user.id, platform="discord")
        
        # Clear any pending messages
        await get_and_delete_pending_messages(interaction.user.id, "discord")

        embed = discord.Embed(
            title="🚫 Onboarding Declined",
            description="No problem! I won't ask you again. If you change your mind, use `/tb_settz` anytime.",
            color=discord.Color.light_grey(),
        )
        await interaction.response.edit_message(embed=embed, view=None)

    @ui.button(label="🔒 Privacy", style=discord.ButtonStyle.secondary)
    async def privacy_info(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="🔒 Privacy & Data",
            description=(
                "**What I store:**\n"
                "• Your Discord User ID and Username.\n"
                "• Your chosen city and timezone.\n"
                "• When you were last active.\n\n"
                "**What I DON'T store:**\n"
                "• Message history.\n"
                "• Personal details beyond city names.\n\n"
                "Data is auto-deleted after 30 days of inactivity."
            ),
            color=discord.Color.dark_grey(),
        )
        await interaction.response.edit_message(
            embed=embed, 
            view=PrivacyBackView(self.target_user_id, self.guild_id)
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            embed = discord.Embed(
                description="❌ This menu is not for you!",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True


class PrivacyBackView(ui.View):
    """View to return to the main onboarding menu from Privacy info."""

    def __init__(self, target_user_id: int, guild_id: Optional[int]):
        super().__init__(timeout=300)
        self.target_user_id = target_user_id
        self.guild_id = guild_id

    @ui.button(label="🔙 Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        user_name = interaction.user.display_name
        embed = get_welcome_embed(user_name)
        await interaction.response.edit_message(
            embed=embed, 
            view=OnboardingMenuView(self.target_user_id, self.guild_id)
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            embed = discord.Embed(
                description="❌ This menu is not for you!",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True


class FallbackView(ui.View):
    """View for fallback options when city is not found."""

    def __init__(self, target_user_id: int):
        super().__init__(timeout=180)
        self.target_user_id = target_user_id

    @ui.button(label="Try Again", style=discord.ButtonStyle.primary)
    async def try_again(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TimezoneModal(origin_interaction=interaction))

    @ui.button(label="Enter Time", style=discord.ButtonStyle.secondary)
    async def manual_time(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TimeInputModal(origin_interaction=interaction))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            embed = discord.Embed(
                description="❌ This button is not for you!",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
