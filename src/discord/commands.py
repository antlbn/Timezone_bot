"""
Discord Slash Commands - mirrors Telegram commands.
"""
import discord
from discord import app_commands, ui

from src.discord import bot
from src.storage import storage
from src import geo
from src.transform import get_utc_offset
from src.logger import get_logger

logger = get_logger()
PLATFORM = "discord"


# =============================================================================
# UI Components (Modals and Views)
# =============================================================================

class TimezoneModal(ui.Modal, title="Set Your Timezone"):
    """Modal for entering city name."""
    
    city = ui.TextInput(
        label="Your City",
        placeholder="e.g. Paris (France), Paris (Texas), London",
        min_length=2,
        max_length=100,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await handle_settz(interaction, self.city.value)

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
        await handle_manual_time(interaction, self.time_str.value)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
        logger.error(f"TimeModal error: {error}", exc_info=error)


class SetTimezoneView(ui.View):
    """View with a button to open the timezone modal."""
    
    def __init__(self, target_user_id: int):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @ui.button(label="Set Timezone", style=discord.ButtonStyle.primary, custom_id="settz_button")
    async def set_tz(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TimezoneModal())

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


# =============================================================================
# Slash Commands
# =============================================================================



@bot.tree.command(name="tb_help", description="Show help menu")
async def cmd_help(interaction: discord.Interaction):
    """Show help menu."""
    help_text = (
        "**Timezone Bot**\n"
        "`/tb_help` - this help\n"
        "`/tb_me` - your location\n"
        "`/tb_settz` - set city\n"
        "`/tb_members` - chat members\n"
        "`/tb_remove` - remove member\n\n"
        "Mention time (14:00) and I'll convert it!"
    )
    await interaction.response.send_message(help_text, ephemeral=True)


@bot.tree.command(name="tb_me", description="Show your current timezone")
async def cmd_me(interaction: discord.Interaction):
    """Show user's current timezone."""
    user = await storage.get_user(interaction.user.id, platform=PLATFORM)
    
    if not user:
        await interaction.response.send_message("Not set. Use `/tb_settz`", ephemeral=True)
        return
    
    await interaction.response.send_message(
        f"{user['city']} {user['flag']} ({user['timezone']})",
        ephemeral=True
    )


async def handle_settz(interaction: discord.Interaction, city: str):
    """Shared logic for setting timezone via command or modal."""
    # Check if interaction was already deferred (slash command) or not (modal)
    if not interaction.response.is_done():
        await interaction.response.defer()
    
    location = geo.get_timezone_by_city(city)
    
    if not location or "error" in location:
        # Show fallback UI with buttons
        await interaction.followup.send(
            f"Could not find '{city}'.\n"
            "Try another name or enter your time manually:",
            view=FallbackView(interaction.user.id)
        )
        return
    
    username = interaction.user.display_name or ""
    
    await storage.set_user(
        user_id=interaction.user.id,
        platform=PLATFORM,
        city=location["city"],
        timezone=location["timezone"],
        flag=location["flag"],
        username=username
    )
    
    # Add to guild members if in a guild
    if interaction.guild:
        await storage.add_chat_member(
            interaction.guild.id,
            interaction.user.id,
            platform=PLATFORM
        )
    
    await interaction.followup.send(
        f"Set: {location['city']} {location['flag']} ({location['timezone']})"
    )
    logger.info(f"[guild:{interaction.guild_id}] User {interaction.user.id} -> {location['timezone']}")


@bot.tree.command(name="tb_settz", description="Set your timezone")
@app_commands.describe(city="Your city name (e.g. Berlin, Tokyo, New York)")
async def cmd_settz(interaction: discord.Interaction, city: str):
    """Set user's timezone by city name."""
    await handle_settz(interaction, city)


async def handle_manual_time(interaction: discord.Interaction, time_str: str):
    """Handle manual time input from modal."""
    # Defer since this might take a moment (though usually fast)
    if not interaction.response.is_done():
        await interaction.response.defer()

    location = geo.resolve_timezone_from_input(time_str)
    
    if not location:
        # Still invalid time - ask to try again
        await interaction.followup.send(
            f"Could not understand time '{time_str}'.\n"
            "Please enter format HH:MM (e.g. 15:30).",
            view=FallbackView(interaction.user.id)
        )
        return
        
    username = interaction.user.display_name or ""
    
    await storage.set_user(
        user_id=interaction.user.id,
        platform=PLATFORM,
        city=location["city"],
        timezone=location["timezone"],
        flag=location["flag"],
        username=username
    )
    
    if interaction.guild:
        await storage.add_chat_member(
            interaction.guild.id,
            interaction.user.id,
            platform=PLATFORM
        )
        
    await interaction.followup.send(
        f"Set: {location['city']} {location['flag']} ({location['timezone']})"
    )
    logger.info(f"[guild:{interaction.guild_id}] User {interaction.user.id} -> {location['timezone']} (manual)")


@bot.tree.command(name="tb_members", description="List server members with timezones")
async def cmd_members(interaction: discord.Interaction):
    """List server members with timezones."""
    if not interaction.guild:
        await interaction.response.send_message("Server only", ephemeral=True)
        return
    
    members = await storage.get_chat_members(interaction.guild.id, platform=PLATFORM)
    
    if not members:
        await interaction.response.send_message("No members yet. Use `/tb_settz`", ephemeral=True)
        return
    
    # Sort by UTC offset
    members.sort(key=lambda m: get_utc_offset(m["timezone"]))
    
    lines = ["**Server members:**"]
    for i, m in enumerate(members, 1):
        flag = m.get("flag", "")
        username = f"@{m['username']}" if m.get("username") else ""
        lines.append(f"{i}. {m['city']} {flag} {username}")
    
    await interaction.response.send_message("\n".join(lines))
