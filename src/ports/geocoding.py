from dataclasses import dataclass
from typing import Protocol

@dataclass
class Location:
    city: str
    timezone: str
    country_code: str
    flag: str | None = None

class GeoPort(Protocol):
    async def resolve_city(self, name: str) -> Location | None:
        ...
