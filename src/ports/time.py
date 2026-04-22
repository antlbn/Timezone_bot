from abc import ABC, abstractmethod
from datetime import datetime


class TimePort(ABC):
    @abstractmethod
    def now_utc(self) -> datetime:
        """Return current time in UTC with timezone info."""
        pass

    @abstractmethod
    def now_tz(self, tz_name: str) -> datetime:
        """Return current time in a specific timezone."""
        pass
