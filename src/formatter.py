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
    converted, offset = convert_time(original_time, sender_tz, target_tz)
    
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


def format_conversion_reply(
    original_time: str,
    sender_city: str,
    sender_tz: str,
    sender_flag: str,
    members: list[dict],
    sender_name: str = ""
) -> str:
    """
    Format according to spec with username:
    Anton: 10:30 Sarajevo 🇧🇦 | 16:30 Paris 🇫🇷 | 18:30 Moscow 🇷🇺
    /tb_help
    """
    settings = get_bot_settings()
    display_limit = settings.get("display_limit_per_chat", 10)
    # 0 means no limit
    if display_limit == 0:
        display_limit = len(members) + 1  # effectively unlimited
    show_usernames = settings.get("show_usernames", False)
    
    # Filter out sender from members (avoid self-conversion)
    other_members = [m for m in members if m["city"] != sender_city]
    
    # Format sender part (always shown)
    sender_part = _format_sender_part(original_time, sender_city, sender_flag, sender_name)
    
    # If no other members to convert
    if not other_members:
        return f"{sender_part}\n/tb_help"
    
    # Sorter and grouping logic
    # Note: We sort filtered members first if needed, but _group_and_sort handles grouping
    # But spec says "Sort by UTC offset" for the list. 
    # Actually _group_and_sort does sorting of keys.
    # We should probably filter -> sort logic
    # The original code did: other_members.sort(key=get_utc_offset) then group.
    
    # Let's perform grouping
    sorted_groups = _group_and_sort_members(other_members, display_limit)
    
    parts = []
    for tz, group in sorted_groups:
        part = _format_tz_group(original_time, sender_tz, tz, group, show_usernames)
        parts.append(part)
    
    # Combine everything
    line = sender_part + " | " + " | ".join(parts)
    
    # Add truncation indicator
    if len(other_members) > display_limit:
        line += f" | ... +{len(other_members) - display_limit} more"
    
    return f"{line}\n/tb_help"
