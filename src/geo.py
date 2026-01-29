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
