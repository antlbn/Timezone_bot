"""
Formatter module.
Builds reply messages according to 07_response_format.md spec.
"""
from src.config import get_bot_settings
from src.transform import convert_time, get_utc_offset, parse_time_string



from src.logger import get_logger

logger = get_logger()

def normalize_time(time_str: str) -> str:
    """Normalize time string to 24h format (e.g. '5 pm' → '17:00')."""
    try:
        t = parse_time_string(time_str)
        return t.strftime("%H:%M")
    except Exception as e:
        logger.debug(f"Time normalization failed for '{time_str}': {e}")
        return time_str  # fallback to original if parsing fails



def _format_sender_part(original_time: str, city: str, flag: str, name: str) -> str:
    """Format the sender's part of the message."""
    normalized = normalize_time(original_time)
    text = f"{normalized} {city} {flag}"
    if name:
        return f"{name}: {text}"
    return text


def _group_and_sort_members(members: list[dict], limit: int) -> list[tuple[str, list[dict]]]:
    """Group members by timezone and sort by UTC offset."""
    tz_groups: dict[str, list] = {}
    
    # Grouping
    for member in members[:limit]:
        tz = member["timezone"]
        if tz not in tz_groups:
            tz_groups[tz] = []
        tz_groups[tz].append(member)
    
    # Sorting by offset
    sorted_tzs = sorted(tz_groups.keys(), key=get_utc_offset)
    return [(tz, tz_groups[tz]) for tz in sorted_tzs]


def _format_tz_group(
    original_time: str, 
    sender_tz: str, 
    target_tz: str, 
    group: list[dict],
    show_usernames: bool
) -> str:
    """Format a single timezone group result."""
    try:
        converted, offset = convert_time(original_time, sender_tz, target_tz)
    except Exception as e:
        logger.error(f"Format group conversion failed for '{original_time}': {e}")
        converted, offset = original_time, 0
    
    # Handle day offset indicator
    if offset == 1:
        time_display = f"{converted}⁺¹"
    elif offset == -1:
        time_display = f"{converted}⁻¹"
    else:
        time_display = converted
    
    cities = ", ".join(m['city'] for m in group)
    flag = group[0].get('flag', '')
    
    part = f"{time_display} {cities} {flag}"
    
    if show_usernames:
        usernames = [f"@{m['username']}" for m in group if m.get('username')]
        if usernames:
            part += f" {', '.join(usernames)}"
            
    return part


def format_single_point_line(
    original_time: str,
    sender_city: str,
    sender_tz: str,
    sender_flag: str,
    members: list[dict],
    show_sender_info: bool = True
) -> str:
    """Format a single line of conversions for one time point."""
    settings = get_bot_settings()
    display_limit = settings.get("display_limit_per_chat", 10)
    if display_limit == 0:
        display_limit = len(members) + 1
    show_usernames = settings.get("show_usernames", False)

    # Filter out sender from members
    other_members = [m for m in members if m["city"] != sender_city]
    
    # Format sender part
    sender_part = _format_sender_part(original_time, sender_city, sender_flag, name="")
    
    if not other_members:
        return sender_part
    
    # Group members by timezone and sort by UTC offset
    sorted_groups = _group_and_sort_members(other_members, display_limit)
    
    parts = []
    for tz, group in sorted_groups:
        part = _format_tz_group(original_time, sender_tz, tz, group, show_usernames)
        parts.append(part)
    
    line = sender_part + " | " + " | ".join(parts)
    
    if len(other_members) > display_limit:
        line += f" | ... +{len(other_members) - display_limit} more"
        
    return line


def format_multi_conversion(
    conversions: list[dict],
    members: list[dict],
    sender_name: str = ""
) -> str:
    """
    Format multiple time points into a single beautiful message.
    Format:
    Anton: 10:30 Sarajevo 🇧🇦 | 12:30 London 🇬🇧
           15:00 Sarajevo 🇧🇦 | 17:00 London 🇬🇧
    /tb_help
    """
    lines = []
    
    if sender_name:
        lines.append(f"*{sender_name}:*")
    
    for conv in conversions:
        point_line = format_single_point_line(
            conv["original_time"],
            conv["source_city"],
            conv["source_tz"],
            conv["source_flag"],
            members
        )
        lines.append(point_line)
            
    return "\n".join(lines)


def format_conversion_reply(
    original_time: str,
    sender_city: str,
    sender_tz: str,
    sender_flag: str,
    members: list[dict],
    sender_name: str = ""
) -> str:
    """Format a single time point conversion (legacy/helper)."""
    conversions = [{
        "original_time": original_time,
        "source_city": sender_city,
        "source_tz": sender_tz,
        "source_flag": sender_flag
    }]
    return format_multi_conversion(conversions, members, sender_name)
