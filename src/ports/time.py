from typing import Protocol
from datetime import datetime

class TimePort(Protocol):
    def now_utc(self) -> datetime:
        """Return current time in UTC with timezone info."""
        ...

    def now_tz(self, tz_name: str) -> datetime:
        """Return current time in a specific timezone."""
        ...
