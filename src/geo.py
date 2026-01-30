"""
Geo module.
City to timezone mapping using Nominatim and TimezoneFinder.
"""
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Initialize clients
_geolocator = Nominatim(user_agent="timezone_bot", timeout=5)
_tf = TimezoneFinder()


def get_country_flag(country_code: str) -> str:
    """Convert ISO country code to emoji flag."""
    if not country_code or len(country_code) != 2:
        return ""
    return "".join(chr(ord(c) + 127397) for c in country_code.upper())


def get_timezone_by_city(city_name: str) -> dict | None:
    """
    Look up timezone by city name.
    
    Args:
        city_name: Name of city (e.g. "Berlin", "New York")
        
    Returns:
        Dict with city, timezone, country, flag or None if not found
    """
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
            "display_name": location.address.split(",")[0]  # Short name
        }
        
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        # Log error but return None to trigger fallback
        return None


def get_multiple_locations(city_name: str, limit: int = 5) -> list[dict]:
    """
    Get multiple location options for a city name.
    Used for disambiguation when city name is ambiguous.
    """
    try:
        locations = _geolocator.geocode(
            city_name, 
            exactly_one=False, 
            limit=limit,
            language="en",
            addressdetails=True
        )
        
        if not locations:
            return []
        
        results = []
        for loc in locations:
            tz = _tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
            if tz:
                address = loc.raw.get("address", {})
                country_code = address.get("country_code", "").upper()
                results.append({
                    "city": city_name.title(),
                    "timezone": tz,
                    "country_code": country_code,
                    "flag": get_country_flag(country_code),
                    "display_name": loc.address
                })
        
        return results
        
    except (GeocoderTimedOut, GeocoderServiceError):
        return []


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
        "offset": rounded_offset
    }
