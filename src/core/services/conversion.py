from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_utc_offset(tz_name: str, now: datetime | None = None) -> float:
    """Get UTC offset in hours for sorting timezones."""
    try:
        tz = ZoneInfo(tz_name)
        if now is None:
            now = datetime.now(tz)
        else:
            now = now.astimezone(tz)
        offset: timedelta | None = now.utcoffset()
        if offset is None:
            return 0
        return offset.total_seconds() / 3600
    except (ValueError, ZoneInfoNotFoundError):
        return 0


def parse_time(time_str: str) -> time | None:
    """
    Parse a time string into a time object.
    Supports: HH:MM, H:MM AM/PM, H AM/PM
    """
    time_str = time_str.strip().upper()

    try:
        # Try 24h format first (HH:MM)
        if ":" in time_str and "AM" not in time_str and "PM" not in time_str:
            parts = time_str.split(":")
            return time(int(parts[0]), int(parts[1]))

        # 12h format with AM/PM
        is_pm = "PM" in time_str
        time_str = time_str.replace("AM", "").replace("PM", "").strip()

        if ":" in time_str:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
        else:
            hour = int(time_str)
            minute = 0

        # Convert to 24h
        if is_pm and hour != 12:
            hour += 12
        elif not is_pm and hour == 12:
            hour = 0

        return time(hour, minute)
    except ValueError:
        return None


def convert_time(
    time_str: str, from_tz: str, to_tz: str, reference_date: datetime
) -> tuple[str, int]:
    """
    Convert time from one timezone to another.

    Returns:
        Tuple of (converted_time_str, day_offset)
    """

    t = parse_time(time_str)
    if t is None:
        raise ValueError(f"Invalid time format: {time_str}")

    source_tz = ZoneInfo(from_tz)
    target_tz = ZoneInfo(to_tz)

    source_dt = datetime.combine(reference_date.date(), t, tzinfo=source_tz)
    target_dt = source_dt.astimezone(target_tz)

    day_offset = (target_dt.date() - source_dt.date()).days
    result_time = target_dt.strftime("%H:%M")

    return result_time, day_offset
