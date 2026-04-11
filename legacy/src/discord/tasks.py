"""
Discord Background Tasks — periodic member sync and inactive user cleanup.
"""

from discord.ext import tasks
from src.discord import bot
from src.storage import storage
from src.config import get_inactive_user_retention_days
from src.logger import get_logger

logger = get_logger()
PLATFORM = "discord"


@tasks.loop(hours=24)
async def sync_discord_members():
    """
    Daily sync to prune members who left while the bot was offline.
    """
    await bot.wait_until_ready()
    logger.info("Starting background Discord member sync...")
    guilds = bot.guilds
    total_removed = 0

    for guild in guilds:
        try:
            db_members = await storage.get_chat_members(guild.id, platform=PLATFORM)
            for m in db_members:
                user_id = m["user_id"]
                # get_member relies on cache, fetch_member is API call.
                # Since this is a daily task, fetch_member is safer but slower.
                # We use get_member first as it's free.
                if not guild.get_member(user_id):
                    # Double check with API if not in cache (to be absolutely sure)
                    try:
                        await guild.fetch_member(user_id)
                    except Exception:
                        # Member really gone
                        await storage.remove_chat_member(
                            guild.id, user_id, platform=PLATFORM
                        )
                        total_removed += 1
                        logger.debug(
                            f"[guild:{guild.id}] Pruned stale member {user_id}"
                        )
        except Exception as e:
            logger.error(f"Error syncing members for guild {guild.id}: {e}")

    logger.info(f"Finished Discord member sync. Total pruned: {total_removed}")


@tasks.loop(hours=24)
async def cleanup_inactive_users():
    """
    Daily cleanup of users who haven't interacted with the bot.
    """
    await bot.wait_until_ready()
    days = get_inactive_user_retention_days()
    if days <= 0:
        logger.debug("Inactive user cleanup disabled (retention_days <= 0)")
        return

    logger.info(f"Starting background cleanup of users inactive for {days} days...")
    try:
        count = await storage.delete_inactive_users(days)
        if count > 0:
            logger.info(f"Cleanup finished. Removed {count} inactive users.")
    except Exception as e:
        logger.error(f"Error during inactive user cleanup: {e}")


def start_tasks():
    """Initialize and start all background tasks."""
    sync_discord_members.start()
    cleanup_inactive_users.start()
    logger.info("Discord background tasks started")
