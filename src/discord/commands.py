"""
Discord Slash Commands - mirrors Telegram commands.
"""

import discord
from discord import app_commands

from src.discord import bot
from src.discord.ui import FallbackView
from src.storage import storage
from src.storage.user_cache import get_user_cached, invalidate_user_cache
from src.storage.pending import get_and_delete_pending_messages
from src.event_detection import process_message
from src import geo
from src.services.user_service import get_sorted_chat_members
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
    user = await get_user_cached(interaction.user.id, platform=PLATFORM)

    if not user:
        await interaction.response.send_message(
            "Not set. Use `/tb_settz`", ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"{user['city']} {user['flag']} ({user['timezone']})", ephemeral=True
    )


async def handle_settz(interaction: discord.Interaction, city: str, origin_interaction: discord.Interaction = None):
    """Shared logic for setting timezone via command or modal."""
    # Check if interaction was already deferred (slash command) or not (modal)
    if not interaction.response.is_done():
        await interaction.response.defer()

    # If this interaction came from a component (like an inline button opening a modal),
    # clean up the original ephemeral message that housed the button.
    if origin_interaction:
        try:
            await origin_interaction.delete_original_response()
        except Exception as e:
            logger.debug(f"Could not delete origin ephemeral message: {e}")
    elif interaction.message:
        try:
            await interaction.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete message: {e}")

    location = geo.get_timezone_by_city(city)

    if not location or "error" in location:
        # Show fallback UI with buttons
        embed = discord.Embed(
            title="📍 City Not Found",
            description=(
                f"Could not find **'{city}'**.\n\n"
                "Try another name or enter your current time manually to help me find your timezone."
            ),
            color=discord.Color.red(),
        )
        await interaction.followup.send(
            embed=embed,
            view=FallbackView(interaction.user.id),
            ephemeral=True,
        )
        return

    username = interaction.user.display_name or ""

    await storage.set_user(
        user_id=interaction.user.id,
        platform=PLATFORM,
        city=location["city"],
        timezone=location["timezone"],
        flag=location["flag"],
        username=username,
    )
    invalidate_user_cache(interaction.user.id, platform=PLATFORM)

    # Add to guild members if in a guild
    if interaction.guild:
        await storage.add_chat_member(
            interaction.guild.id, interaction.user.id, platform=PLATFORM
        )

    embed = discord.Embed(
        title="✅ Timezone Set!",
        description=f"Your location is now **{location['city']} {location['flag']}**\nTimezone: `{location['timezone']}`",
        color=discord.Color.green(),
    )
    await interaction.followup.send(embed=embed, ephemeral=True)
    logger.info(
        f"[guild:{interaction.guild_id}] User {interaction.user.id} -> {location['timezone']}"
    )

    # 2. Process pending message
    await _process_discord_pending(interaction)


async def _process_discord_pending(interaction: discord.Interaction):
    """Helper to check for and process pending Discord messages."""
    pending_list = await get_and_delete_pending_messages(interaction.user.id, PLATFORM)
    if not pending_list:
        return

    logger.info(
        f"[guild:{interaction.guild_id}] Processing {len(pending_list)} pending messages for user {interaction.user.id}"
    )

    # Re-fetch user record from CACHE
    user_record = await get_user_cached(interaction.user.id, platform=PLATFORM)

    for pending in pending_list:
        # Build send_reply_fn using MessageReference.
        # NOTE: Default argument `_pending=pending` is intentional — it captures
        # the current loop variable by value, avoiding the classic Python
        # closure-in-loop bug where all closures would share the last `pending`.
        async def send_reply_fn(text: str, _pending: dict = pending) -> None:
            # IMPORTANT: Releasing from queue must use the original channel
            # to allow replying to the original message.
            original_channel_id = int(
                _pending.get("channel_id") or _pending["chat_id"]
            )
            channel = bot.get_channel(original_channel_id)

            if not channel:
                # If bot doesn't "see" it in cache, try fetching it
                try:
                    channel = await bot.fetch_channel(original_channel_id)
                except Exception:
                    logger.error(f"Could not fetch channel {original_channel_id}")
                    return

            if channel:
                message_ref = discord.MessageReference(
                    message_id=int(_pending["message_id"]),
                    channel_id=original_channel_id,
                    guild_id=interaction.guild_id,
                )
                embed = discord.Embed(
                    description=text,
                    color=discord.Color.green(),
                )
                sent = await channel.send(embed=embed, reference=message_ref)
                return str(sent.id)
            else:
                logger.error(
                    f"Could not find channel {_pending['chat_id']} to send pending reply"
                )
                return None

        async def edit_reply_fn(message_id: str, new_text: str) -> None:
            if channel:
                try:
                    prev = await channel.fetch_message(int(message_id))
                    new_embed = discord.Embed(
                        description=new_text,
                        color=discord.Color.green(),
                    )
                    await prev.edit(embed=new_embed)
                except Exception as e:
                    logger.warning(f"edit_reply_fn failed for msg {message_id}: {e}")
                    raise

        try:
            await process_message(
                message_text=pending["text"],
                chat_id=str(pending["chat_id"]),
                user_id=str(interaction.user.id),
                platform=PLATFORM,
                author_name=pending["author_name"],
                timestamp_utc=pending["timestamp_utc"],
                sender_db=user_record,
                send_fn=send_reply_fn,
                edit_fn=edit_reply_fn,
                skip_history_append=True,
                skip_aging=True,
                precomputed_snapshot=pending.get("snapshot"),
            )

        except Exception as e:
            logger.error(
                f"[guild:{interaction.guild_id}] Failed to process pending message "
                f"{pending.get('message_id')}: {e}",
                exc_info=True,
            )


@bot.tree.command(name="tb_settz", description="Set your timezone")
@app_commands.describe(city="Your city name (e.g. Berlin, Tokyo, New York)")
async def cmd_settz(interaction: discord.Interaction, city: str):
    """Set user's timezone by city name."""
    await handle_settz(interaction, city)


async def handle_manual_time(interaction: discord.Interaction, time_str: str, origin_interaction: discord.Interaction = None):
    """Handle manual time input from modal."""
    # Defer since this might take a moment (though usually fast)
    if not interaction.response.is_done():
        await interaction.response.defer()

    if origin_interaction:
        try:
            await origin_interaction.delete_original_response()
        except Exception as e:
            logger.debug(f"Could not delete origin ephemeral message: {e}")
    elif interaction.message:
        try:
            await interaction.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete origin ephemeral message: {e}")

    location = geo.resolve_timezone_from_input(time_str)

    if not location:
        # Still invalid time - ask to try again
        embed = discord.Embed(
            title="⏰ Invalid Time Format",
            description=(
                f"Could not understand time **'{time_str}'**.\n\n"
                "Please enter time in **HH:MM** format (e.g., `15:30` or `09:15`)."
            ),
            color=discord.Color.red(),
        )
        await interaction.followup.send(
            embed=embed,
            view=FallbackView(interaction.user.id),
            ephemeral=True,
        )
        return

    username = interaction.user.display_name or ""

    await storage.set_user(
        user_id=interaction.user.id,
        platform=PLATFORM,
        city=location["city"],
        timezone=location["timezone"],
        flag=location["flag"],
        username=username,
    )
    invalidate_user_cache(interaction.user.id, platform=PLATFORM)

    if interaction.guild:
        await storage.add_chat_member(
            interaction.guild.id, interaction.user.id, platform=PLATFORM
        )

    embed = discord.Embed(
        title="✅ Timezone Set!",
        description=f"Your location is now **{location['city']} {location['flag']}**\nTimezone: `{location['timezone']}`",
        color=discord.Color.green(),
    )
    await interaction.followup.send(embed=embed, ephemeral=True)
    logger.info(
        f"[guild:{interaction.guild_id}] User {interaction.user.id} -> {location['timezone']} (manual)"
    )

    # Process pending message
    await _process_discord_pending(interaction)


@bot.tree.command(name="tb_members", description="List server members with timezones")
async def cmd_members(interaction: discord.Interaction):
    """List server members with timezones."""
    if not interaction.guild:
        await interaction.response.send_message("Server only", ephemeral=True)
        return

    members = await get_sorted_chat_members(interaction.guild.id, platform=PLATFORM)

    if not members:
        await interaction.response.send_message(
            "No members yet. Use `/tb_settz`", ephemeral=True
        )
        return

    lines = ["**Server members:**"]
    for i, m in enumerate(members, 1):
        flag = m.get("flag", "")
        username = f"@{m['username']}" if m.get("username") else ""
        lines.append(f"{i}. {m['city']} {flag} {username}")

    await interaction.response.send_message("\n".join(lines))
