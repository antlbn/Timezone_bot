"""
Formatter module.
Builds reply messages according to 07_response_format.md spec.
"""
from src.config import get_bot_settings
from src.transform import convert_time, format_time_with_offset, get_utc_offset


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
    
    # Filter out sender from members
    other_members = [m for m in members if m["city"] != sender_city]
    
    # If no other members, just show sender
    if not other_members:
        sender_part = f"{original_time} {sender_city} {sender_flag}"
        if sender_name:
            sender_part = f"{sender_name}: {sender_part}"
        return f"{sender_part}\n/tb_help"
    
    # Sort by UTC offset (spec requirement)
    other_members.sort(key=lambda m: get_utc_offset(m["timezone"]))
    
    # Group by timezone
    tz_groups: dict[str, list] = {}
    for member in other_members[:display_limit]:
        tz = member["timezone"]
        if tz not in tz_groups:
            tz_groups[tz] = []
        tz_groups[tz].append(member)
    
    # Sort groups by offset
    sorted_tzs = sorted(tz_groups.keys(), key=get_utc_offset)
    
    # Build parts
    show_usernames = settings.get("show_usernames", False)
    
    parts = []
    for tz in sorted_tzs:
        group = tz_groups[tz]
        converted, offset = convert_time(original_time, sender_tz, tz)
        
        if offset == 1:
            time_display = f"{converted}⁺¹"
        elif offset == -1:
            time_display = f"{converted}⁻¹"
        else:
            time_display = converted
        
        cities = ", ".join(m['city'] for m in group)
        flag = group[0].get('flag', '')
        
        part = f"{time_display} {cities} {flag}"
        
        # Add usernames if enabled
        if show_usernames:
            usernames = [f"@{m['username']}" for m in group if m.get('username')]
            if usernames:
                part += f" {', '.join(usernames)}"
        
        parts.append(part)
    
    # Build output
    sender_part = f"{original_time} {sender_city} {sender_flag}"
    if sender_name:
        sender_part = f"{sender_name}: {sender_part}"
    
    line = sender_part + " | " + " | ".join(parts)
    
    if len(other_members) > display_limit:
        line += f" | ... +{len(other_members) - display_limit} more"
    
    return f"{line}\n/tb_help"
