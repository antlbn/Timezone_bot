"""
Geo module.
City to timezone mapping using Nominatim and TimezoneFinder.
"""

import asyncio
import time
from collections import OrderedDict

from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


# Initialize logger
from src.logger import get_logger

logger = get_logger()

# Initialize clients
_geolocator = Nominatim(user_agent="timezone_bot", timeout=5)
_tf = TimezoneFinder()
_city_cache: OrderedDict[str, dict | None] = OrderedDict()
_CITY_CACHE_MAX = 256


def get_country_flag(country_code: str) -> str:
    """Convert ISO country code to emoji flag."""
    if not country_code or len(country_code) != 2:
        return ""
    return "".join(chr(ord(c) + 127397) for c in country_code.upper())


def _normalize_city_key(city_name: str) -> str:
    """Normalize user-entered city text for cache lookup."""
    return city_name.strip().casefold()


def _lookup_city_uncached(city_name: str) -> dict | None:
    """Blocking city lookup implementation used behind sync/async wrappers."""
    try:
        location = _geolocator.geocode(city_name, language="en", addressdetails=True)

        if not location:
            return None

        # Get timezone from coordinates
        timezone = _tf.timezone_at(lat=location.latitude, lng=location.longitude)

        if not timezone:
            return None

        # Extract country code
        address = location.raw.get("address", {})
        country_code = address.get("country_code", "").upper()

        return {
            "city": city_name.title(),
            "timezone": timezone,
            "country_code": country_code,
            "flag": get_country_flag(country_code),
            "display_name": location.address.split(",")[0],  # Short name
        }

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.error(f"Geocoding error for '{city_name}': {e}")
        return {"error": "Geocoding service unavailable", "details": str(e)}


def get_timezone_by_city(city_name: str) -> dict | None:
    """
    Look up timezone by city name.

    Args:
        city_name: Name of city (e.g. "Berlin", "New York")

    Returns:
        Dict with city, timezone, country, flag or None if not found
    """
    key = _normalize_city_key(city_name)
    if not key:
        return None

    if key in _city_cache:
        _city_cache.move_to_end(key)
        cached = _city_cache[key]
        return dict(cached) if isinstance(cached, dict) else cached

    result = _lookup_city_uncached(city_name)

    # Cache stable outcomes only. Do not cache transient provider errors.
    if result is None or (isinstance(result, dict) and "error" not in result):
        _city_cache[key] = result
        _city_cache.move_to_end(key)
        if len(_city_cache) > _CITY_CACHE_MAX:
            _city_cache.popitem(last=False)

    return result


async def aget_timezone_by_city(city_name: str) -> dict | None:
    """Async wrapper for city lookup that keeps blocking geocoding off the event loop."""
    started = time.perf_counter()
    result = await asyncio.to_thread(get_timezone_by_city, city_name)
    elapsed = time.perf_counter() - started
    if elapsed > 1.0:
        logger.warning(f"Slow geocoding lookup for '{city_name}' took {elapsed:.2f}s")
    return result


# Common timezones by UTC offset (for fallback)
OFFSET_TO_TIMEZONE = {
    -12: "Etc/GMT+12",
    -11: "Pacific/Midway",
    -10: "Pacific/Honolulu",
    -9: "America/Anchorage",
    -8: "America/Los_Angeles",
    -7: "America/Denver",
    -6: "America/Chicago",
    -5: "America/New_York",
    -4: "America/Halifax",
    -3: "America/Sao_Paulo",
    -2: "Atlantic/South_Georgia",
    -1: "Atlantic/Azores",
    0: "Europe/London",
    1: "Europe/Paris",
    2: "Europe/Helsinki",
    3: "Europe/Moscow",
    4: "Asia/Dubai",
    5: "Asia/Karachi",
    6: "Asia/Dhaka",
    7: "Asia/Bangkok",
    8: "Asia/Singapore",
    9: "Asia/Tokyo",
    10: "Australia/Sydney",
    11: "Pacific/Noumea",
    12: "Pacific/Auckland",
}


def get_timezone_by_offset(offset_hours: float) -> dict:
    """
    Find IANA timezone matching given UTC offset.

    Args:
        offset_hours: UTC offset in hours (e.g. 3.0 for UTC+3)

    Returns:
        Dict with timezone and display info
    """
    # Round to nearest integer
    rounded_offset = round(offset_hours)

    # Clamp to valid range
    rounded_offset = max(-12, min(12, rounded_offset))

    timezone = OFFSET_TO_TIMEZONE.get(rounded_offset, "Etc/UTC")

    # Format offset for display
    sign = "+" if rounded_offset >= 0 else ""
    city_name = f"UTC{sign}{rounded_offset}"

    return {
        "city": city_name,
        "timezone": timezone,
        "flag": "🌐",
        "offset": rounded_offset,
    }


def _extract_times_for_resolver(text: str) -> list[str]:
    """Internal helper to extract time for manual offset resolution."""
    import re

    patterns = [
        r"\b([0-1]?[0-9]|2[0-3]):([0-5][0-9])\b",
        r"\b((1[0-2]|0?[1-9]):([0-5][0-9])\s?([AaPp][Mm]))\b",
        r"\b((1[0-2]|0?[1-9])\s?([AaPp][Mm]))\b",
    ]
    matches = []
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            matches.append(m.group(0))
    return matches


def resolve_timezone_from_input(user_input: str) -> dict | None:
    """
    Universal timezone resolver: checks TIME pattern first (via regex),
    then falls back to city geocoding.

    This order prevents false geo matches like '19:53' -> Jakarta.

    Args:
        user_input: City name OR current time string (e.g. "Berlin" or "15:30")

    Returns:
        Location dict with city/timezone/flag, or None if unresolved
    """
    from datetime import datetime, timezone as tz
    from src.transform import parse_time_string

    user_input = user_input.strip()

    # 1. Check if input matches time pattern (regex) — FIRST
    times = _extract_times_for_resolver(user_input)
    if times:
        try:
            user_time = parse_time_string(times[0])
            now_utc = datetime.now(tz.utc)

            # Calculate offset in hours
            utc_hours = now_utc.hour + now_utc.minute / 60
            user_hours = user_time.hour + user_time.minute / 60
            offset = user_hours - utc_hours

            logger.debug(
                f"Offset calc: user_input='{user_input}' user_time={user_time} utc_now={now_utc.strftime('%H:%M')} offset={offset:.2f}"
            )

            # Handle day boundary
            if offset > 12:
                offset -= 24
            elif offset < -12:
                offset += 24

            logger.debug(f"Final offset after boundary: {offset:.2f}")

            return get_timezone_by_offset(offset)

        except Exception as e:
            logger.error(f"Time parsing error: {e}")
            # Fall through to city lookup

    # 2. Not a time pattern — try city geocoding
    location = get_timezone_by_city(user_input)
    if location and "error" not in location:
        return location

    return None


async def aresolve_timezone_from_input(user_input: str) -> dict | None:
    """Async wrapper for mixed time/city resolution."""
    started = time.perf_counter()
    result = await asyncio.to_thread(resolve_timezone_from_input, user_input)
    elapsed = time.perf_counter() - started
    if elapsed > 1.0 and not _extract_times_for_resolver(user_input):
        logger.warning(f"Slow timezone resolution for '{user_input}' took {elapsed:.2f}s")
    return result
