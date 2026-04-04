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


def _format_sender_part_compact(original_time: str, city: str) -> str:
    """Format the sender/source segment for compact inline rendering."""
    normalized = normalize_time(original_time)
    return f"{normalized} {city}"


def _group_and_sort_members(
    members: list[dict], limit: int
) -> list[tuple[str, list[dict]]]:
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
    show_usernames: bool,
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

    cities = ", ".join(m["city"] for m in group)
    flag = group[0].get("flag", "")

    part = f"{time_display} {cities} {flag}"

    if show_usernames:
        usernames = [f"@{m['username']}" for m in group if m.get("username")]
        if usernames:
            part += f" {', '.join(usernames)}"

    return part


def _format_tz_group_compact(
    original_time: str,
    sender_tz: str,
    target_tz: str,
    group: list[dict],
    show_usernames: bool,
) -> str:
    """Format a single timezone group in compact inline style."""
    try:
        converted, offset = convert_time(original_time, sender_tz, target_tz)
    except Exception as e:
        logger.error(f"Format group conversion failed for '{original_time}': {e}")
        converted, offset = original_time, 0

    if offset == 1:
        time_display = f"{converted}⁺¹"
    elif offset == -1:
        time_display = f"{converted}⁻¹"
    else:
        time_display = converted

    cities = ", ".join(m["city"] for m in group)
    part = f"{time_display} {cities}"

    if show_usernames:
        usernames = [f"@{m['username']}" for m in group if m.get("username")]
        if usernames:
            part += f" {' '.join(usernames)}"

    return part


def format_single_point_line(
    original_time: str,
    sender_city: str,
    sender_tz: str,
    sender_flag: str,
    members: list[dict],
    event_type: str = "",
    show_sender_info: bool = True,
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

    # Combine sender and other parts
    all_parts = [sender_part]

    if other_members:
        # Group members by timezone and sort by UTC offset
        sorted_groups = _group_and_sort_members(other_members, display_limit)
        for tz, group in sorted_groups:
            part = _format_tz_group(original_time, sender_tz, tz, group, show_usernames)
            all_parts.append(part)

    if event_type:
        all_parts.insert(0, event_type)

    if len(other_members) > display_limit:
        all_parts.append(f"... +{len(other_members) - display_limit} more")

    # Vertical list for maximum mobile readability
    return "\n".join(all_parts)


def format_single_point_compact(
    original_time: str,
    sender_city: str,
    sender_tz: str,
    members: list[dict],
    event_type: str = "",
) -> str:
    """Format one time point as a single compact line."""
    settings = get_bot_settings()
    display_limit = settings.get("display_limit_per_chat", 10)
    if display_limit == 0:
        display_limit = len(members) + 1
    show_usernames = settings.get("show_usernames", False)

    other_members = [m for m in members if m["city"] != sender_city]
    parts = [_format_sender_part_compact(original_time, sender_city)]

    if other_members:
        sorted_groups = _group_and_sort_members(other_members, display_limit)
        for tz, group in sorted_groups:
            parts.append(
                _format_tz_group_compact(
                    original_time, sender_tz, tz, group, show_usernames
                )
            )

    line = ", ".join(parts)

    if event_type:
        line = f"{event_type} | {line}"

    if len(other_members) > display_limit:
        line += f", ... +{len(other_members) - display_limit} more"

    return line


def format_multi_conversion(
    conversions: list[dict], members: list[dict], sender_name: str = "", footer: str | None = None
) -> str:
    """
    Format multiple time points into a single beautiful message.
    Rendering mode is controlled by bot.render_mode in configuration.yaml.
    """
    settings = get_bot_settings()
    render_mode = settings.get("render_mode", "vertical")
    show_sender_prefix = settings.get("show_sender_prefix", False)
    compact_code_block = settings.get(
        "compact_inline_code_block",
        settings.get("compact_inline_monospace", False),
    )
    point_lines = []

    for conv in conversions:
        if render_mode == "compact_inline":
            point_text = format_single_point_compact(
                conv["original_time"],
                conv["source_city"],
                conv["source_tz"],
                members,
                event_type=conv.get("event_type", ""),
            )
        else:
            point_text = format_single_point_line(
                conv["original_time"],
                conv["source_city"],
                conv["source_tz"],
                conv["source_flag"],
                members,
                event_type=conv.get("event_type", ""),
            )
        point_lines.append(point_text)

    separator = "\n" if render_mode == "compact_inline" else "\n\n"
    body = separator.join(point_lines)

    if render_mode == "compact_inline" and compact_code_block:
        body = f"```\n{body}\n```"
    
    if footer:
        body += f"\n**{footer}**"

    if sender_name and show_sender_prefix:
        return f"{sender_name}: {body}"
    return body


def format_conversion_reply(
    original_time: str,
    sender_city: str,
    sender_tz: str,
    sender_flag: str,
    members: list[dict],
    sender_name: str = "",
) -> str:
    """Format a single time point conversion (legacy/helper)."""
    conversions = [
        {
            "original_time": original_time,
            "source_city": sender_city,
            "source_tz": sender_tz,
            "source_flag": sender_flag,
        }
    ]
    return format_multi_conversion(conversions, members, sender_name)
