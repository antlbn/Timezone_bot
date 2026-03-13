"""
tools.py — LLM Tool Implementations

This module contains the server-side implementations of tools the LLM can call.
Each function is invoked by detector.py after the LLM issues a tool_call,
or directly when the provider doesn't support function-calling (JSON-path fallback).
"""
from src.logger import get_logger
from src import formatter
from src.storage import storage

logger = get_logger()


async def execute_convert_time(
    sender_id: str,
    sender_name: str,
    times: list[str],
    cities: list[str | None],
    sender_db: dict,
    platform: str,
    chat_id: str,
    send_fn,  # async callable(text: str) → None
) -> None:
    """
    Convert event time(s) to every chat participant's local time and send the reply.

    Parameters
    ----------
    sender_id   : Platform user ID of the message author.
    sender_name : Display name of the message author.
    times       : List of time strings (HH:MM) from the LLM.
    cities      : Parallel list — city override for each time, or None → sender DB TZ.
    sender_db   : Sender's DB record (must contain at least 'timezone' and 'city').
    platform    : "telegram" | "discord"
    chat_id     : Platform-specific chat/guild ID (string).
    send_fn     : Coroutine that posts a text reply to the chat.
    """
    # Load all registered members of this chat
    members = await storage.get_chat_members(chat_id, platform=platform)
    if not members:
        logger.warning(f"[chat:{chat_id}] convert_time: no members in DB, skipping reply.")
        return

    for i, time_str in enumerate(times):
        city_override = cities[i] if i < len(cities) else None

        # Resolve source timezone for this time entry
        if city_override:
            from src.geo import get_timezone_by_city
            geo_result = get_timezone_by_city(city_override)
            if geo_result and not geo_result.get("error"):
                source_city = geo_result["city"]
                source_tz   = geo_result["timezone"]
                source_flag = geo_result["flag"]
            else:
                logger.warning(
                    f"[chat:{chat_id}] Geocode failed for '{city_override}', "
                    f"falling back to sender DB TZ."
                )
                source_city = sender_db.get("city", "")
                source_tz   = sender_db.get("timezone", "UTC")
                source_flag = sender_db.get("flag", "")
        else:
            source_city = sender_db.get("city", "")
            source_tz   = sender_db.get("timezone", "UTC")
            source_flag = sender_db.get("flag", "")

        reply = formatter.format_conversion_reply(
            time_str,
            source_city,
            source_tz,
            source_flag,
            members,
            sender_name,
        )

        await send_fn(reply)
        logger.debug(
            f"[chat:{chat_id}] Replied: time={time_str}, city={city_override}, "
            f"source_tz={source_tz}"
        )
