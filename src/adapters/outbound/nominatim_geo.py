import asyncio
import logging
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from src.ports.geocoding import GeoPort, Location

logger = logging.getLogger(__name__)
_tf = TimezoneFinder()

def get_country_flag(country_code: str) -> str:
    if not country_code or len(country_code) != 2:
        return ""
    return "".join(chr(ord(c) + 127397) for c in country_code.upper())

class NominatimGeo(GeoPort):
    def _create_geolocator(self) -> Nominatim:
        return Nominatim(user_agent="timezone_bot_v2", timeout=5)

    def _geocode_sync(self, name: str) -> Location | None:
        try:
            geolocator = self._create_geolocator()
            loc = geolocator.geocode(name, language="en", addressdetails=True)
            if not loc:
                return None
            timezone = _tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
            if not timezone:
                return None
            address = loc.raw.get("address", {})
            country_code = address.get("country_code", "").upper()
            return Location(
                city=loc.address.split(",")[0],
                timezone=timezone,
                country_code=country_code,
                flag=get_country_flag(country_code)
            )
        except Exception as e:
            logger.error(f"Geocoding error for '{name}': {e}")
            return None

    async def resolve_city(self, name: str) -> Location | None:
        return await asyncio.to_thread(self._geocode_sync, name)
