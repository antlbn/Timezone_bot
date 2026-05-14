from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from ports.time import TimePort


class RealTimeAdapter(TimePort):
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def now_tz(self, tz_name: str) -> datetime:
        return datetime.now(ZoneInfo(tz_name))
