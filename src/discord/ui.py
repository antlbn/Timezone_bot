"""
Discord UI Components (Modals and Views).
"""
import discord
from discord import ui
from src.logger import get_logger

logger = get_logger()

class TimezoneModal(ui.Modal, title="Set Your Timezone"):
    """Modal for entering city name."""
    
    city = ui.TextInput(
        label="Your City",
        placeholder="e.g. Paris (France), Paris (Texas), London",
        min_length=2,
        max_length=100,
        required=True
    )

    def __init__(self, pending_time: str | None = None):
        super().__init__()
        self.pending_time = pending_time

    async def on_submit(self, interaction: discord.Interaction):
        # Local import to avoid circular dependency
        from src.discord.commands import handle_settz
        await handle_settz(interaction, self.city.value, pending_time=self.pending_time)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
        logger.error(f"Modal error: {error}", exc_info=error)


class TimeInputModal(ui.Modal, title="Enter Time Manually"):
    """Modal for entering time directly."""
    
    time_str = ui.TextInput(
        label="Current Time",
        placeholder="e.g. 15:30",
        min_length=4,
        max_length=5,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Local import to avoid circular dependency
        from src.discord.commands import handle_manual_time
        await handle_manual_time(interaction, self.time_str.value)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
        logger.error(f"TimeModal error: {error}", exc_info=error)


class SetTimezoneView(ui.View):
    """View with a button to open the timezone modal."""
    
    def __init__(self, target_user_id: int, pending_time: str | None = None):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id
        self.pending_time = pending_time

    @ui.button(label="Set Timezone", style=discord.ButtonStyle.primary, custom_id="settz_button")
    async def set_tz(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TimezoneModal(pending_time=self.pending_time))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message("This button is not for you!", ephemeral=True)
            return False
        return True


class FallbackView(ui.View):
    """View for fallback options when city is not found."""
    
    def __init__(self, target_user_id: int):
        super().__init__(timeout=180)
        self.target_user_id = target_user_id

    @ui.button(label="Try Again", style=discord.ButtonStyle.primary)
    async def try_again(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TimezoneModal())

    @ui.button(label="Enter Time", style=discord.ButtonStyle.secondary)
    async def manual_time(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TimeInputModal())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message("This button is not for you!", ephemeral=True)
            return False
        return True
