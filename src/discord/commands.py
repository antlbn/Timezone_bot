"""
Discord Slash Commands - mirrors Telegram commands.
"""
import discord
from discord import app_commands

from src.discord import bot
from src.storage import storage
from src import geo
from src.transform import get_utc_offset
from src.logger import get_logger

logger = get_logger()
PLATFORM = "discord"


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


@bot.tree.command(name="tb_settz", description="Set your timezone")
@app_commands.describe(city="Your city name (e.g. Berlin, Tokyo, New York)")
async def cmd_settz(interaction: discord.Interaction, city: str):
    """Set user's timezone by city name."""
    from src.discord import state
    
    # Defer to avoid 3-second timeout during geocoding
    await interaction.response.defer()
    
    location = geo.get_timezone_by_city(city)
    
    if not location or "error" in location:
        # Set fallback state and ask for time
        state.set_state(
            interaction.user.id, 
            "waiting_for_fallback",
            guild_id=interaction.guild.id if interaction.guild else None
        )
        await interaction.followup.send(
            f"Could not find '{city}'.\n"
            "Reply with your current time (e.g. 15:30) or try another city name."
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


@bot.tree.command(name="tb_remove", description="Remove a member from the list")
@app_commands.describe(number="Member number to remove (from /tb_members list)")
async def cmd_remove(interaction: discord.Interaction, number: int):
    """Remove a member by number."""
    if not interaction.guild:
        await interaction.response.send_message("Server only", ephemeral=True)
        return
    
    members = await storage.get_chat_members(interaction.guild.id, platform=PLATFORM)
    
    if not members:
        await interaction.response.send_message("No members to remove", ephemeral=True)
        return
    
    # Sort same as tb_members
    members.sort(key=lambda m: get_utc_offset(m["timezone"]))
    
    if number < 1 or number > len(members):
        await interaction.response.send_message(
            f"Invalid number. Enter 1-{len(members)}",
            ephemeral=True
        )
        return
    
    user_id = members[number - 1]["user_id"]
    await storage.remove_chat_member(interaction.guild.id, user_id, platform=PLATFORM)
    
    await interaction.response.send_message(f"Removed member #{number}")
    logger.info(f"[guild:{interaction.guild.id}] Removed user {user_id}")
