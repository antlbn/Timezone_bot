"""
Discord Slash Commands - mirrors Telegram commands.
"""
import discord
from discord import app_commands

from src.discord import bot
from src.discord.ui import FallbackView
from src.storage import storage
from src import geo, formatter
from src.transform import get_utc_offset
from src.logger import get_logger

logger = get_logger()
PLATFORM = "discord"



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


async def handle_settz(interaction: discord.Interaction, city: str, pending_time: str | None = None):
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
    
    # Process pending time if present (analogous to Telegram behavior)
    if pending_time and interaction.guild:
        members = await storage.get_chat_members(interaction.guild.id, platform=PLATFORM)
        if members:
            reply = formatter.format_conversion_reply(
                pending_time,
                location["city"],
                location["timezone"],
                location["flag"],
                members,
                username
            )
            await interaction.followup.send(reply)


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
