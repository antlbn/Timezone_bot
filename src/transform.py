"""
Transform module.
Time conversion using UTC-pivot architecture.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import dateparser


def get_utc_offset(tz_name: str) -> float:
    """Get UTC offset in hours for sorting timezones."""
    try:
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
        return now.utcoffset().total_seconds() / 3600
    except Exception:
        return 0


def parse_time_string(time_str: str) -> time:
    """
    Parse a time string into a time object.
    Supports: HH:MM, H:MM AM/PM, H AM/PM, and Natural Language
    """
    time_str_clean = time_str.strip().upper()
    
    # Fast path: Try manual parsing for standard formats to avoid dateparser overhead
    try:
        # Try 24h format first (HH:MM)
        if ":" in time_str_clean and "AM" not in time_str_clean and "PM" not in time_str_clean:
            parts = time_str_clean.split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return time(int(parts[0]), int(parts[1]))
        
        # 12h format with AM/PM
        if "AM" in time_str_clean or "PM" in time_str_clean:
            is_pm = "PM" in time_str_clean
            t_str = time_str_clean.replace("AM", "").replace("PM", "").strip()
            
            if ":" in t_str:
                parts = t_str.split(":")
                hour = int(parts[0])
                minute = int(parts[1])
            else:
                hour = int(t_str)
                minute = 0
            
            # Convert to 24h
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0
            
            return time(hour, minute)
            
    except ValueError:
        pass # Fallthrough to dateparser
    
    # Slow path: Use NLP for natural language ("в 9 вечера")
    try:
        dt = dateparser.parse(time_str, languages=['ru', 'en'])
        if dt:
            return dt.time()
    except Exception:
        pass
        
    # Default fallback (should ideally raise error, but here we return 00:00 or raise)
    raise ValueError(f"Could not parse time: {time_str}")


def convert_time(
    time_str: str,
    from_tz: str,
    to_tz: str,
    reference_date: datetime | None = None
) -> tuple[str, int]:
    """
    Convert time from one timezone to another.
    
    Args:
        time_str: Original time string (e.g. "14:00")
        from_tz: Source IANA timezone (e.g. "Europe/Berlin")
        to_tz: Target IANA timezone (e.g. "America/New_York")
        reference_date: Date context (default: today)
        
    Returns:
        Tuple of (converted_time_str, day_offset)
        day_offset: 0 = same day, +1 = next day, -1 = previous day
    """
    if reference_date is None:
        reference_date = datetime.now()
    
    try:
        # Parse the time
        t = parse_time_string(time_str)
        
        # Create datetime in source timezone
        source_tz = ZoneInfo(from_tz)
        target_tz = ZoneInfo(to_tz)
        
        source_dt = datetime.combine(reference_date.date(), t, tzinfo=source_tz)
        target_dt = source_dt.astimezone(target_tz)
        
        # Calculate day offset
        day_offset = (target_dt.date() - source_dt.date()).days
        
        # Format result
        result_time = target_dt.strftime("%H:%M")
        
        return result_time, day_offset
    except Exception:
        return time_str, 0 # Fail safe


def format_time_with_offset(time_str: str, day_offset: int) -> str:
    """Format time with optional day marker."""
    if day_offset == 1:
        return f"{time_str} (+1)"
    elif day_offset == -1:
        return f"{time_str} (-1)"
    return time_str
