"""
Formatter module.
Builds conversion replies according to 07_response_format.md.
"""

from src.config import get_response_style, get_show_event_title, get_show_usernames
from src.transform import convert_time, get_utc_offset, parse_time_string
from src.logger import get_logger

logger = get_logger()


def normalize_time(time_str: str) -> str:
    """Normalize a time string to 24h format when possible."""
    try:
        t = parse_time_string(time_str)
        return t.strftime("%H:%M")
    except Exception as exc:
        logger.debug(f"Time normalization failed for '{time_str}': {exc}")
        return time_str


def _format_time_with_shift(time_str: str, day_shift: int) -> str:
    normalized = normalize_time(time_str)
    if day_shift == 1:
        return f"{normalized}⁺¹"
    if day_shift == -1:
        return f"{normalized}⁻¹"
    return normalized


def _member_name(member: dict) -> str | None:
    """Render a member name according to the shared output contract."""
    username = member.get("username")
    if username:
        return f"@{username}"
    return member.get("display_name") or member.get("full_name") or member.get("name")


def _format_names(group: list[dict]) -> str:
    names = [name for name in (_member_name(member) for member in group) if name]
    if not names:
        return ""
    if len(names) <= 2:
        return ", ".join(names)
    return f"{names[0]}, {names[1]}, +{len(names) - 2} more"


def _group_members_by_timezone(members: list[dict]) -> list[tuple[str, list[dict]]]:
    tz_groups: dict[str, list[dict]] = {}
    for member in members:
        timezone = member.get("timezone")
        if not timezone:
            continue
        tz_groups.setdefault(timezone, []).append(member)
    return sorted(tz_groups.items(), key=lambda item: get_utc_offset(item[0]))


def _join_city_labels(group: list[dict], fallback_label: str) -> str:
    labels: list[str] = []
    for member in group:
        label = member.get("city") or member.get("label") or member.get("timezone")
        if label and label not in labels:
            labels.append(label)
    if not labels:
        return fallback_label
    return ", ".join(labels)


def _render_row(
    *,
    displayed_time: str,
    label: str,
    flag: str,
    group: list[dict],
    show_usernames: bool,
    prefix: str = "",
) -> str:
    parts = [displayed_time, label]
    if flag:
        parts.append(flag)
    row = " ".join(part for part in parts if part)
    if prefix:
        row = f"{prefix} {row}"
    if show_usernames:
        names = _format_names(group)
        if names:
            row = f"{row} {names}"
    return row


def _build_conversion_rows(
    *,
    original_time: str,
    sender_city: str,
    sender_tz: str,
    sender_flag: str,
    members: list[dict],
) -> list[dict]:
    """Build normalized rows for source and converted timezones."""
    grouped_members = _group_members_by_timezone(members)

    source_group: list[dict] = []
    other_groups: list[tuple[str, list[dict]]] = []
    for timezone, group in grouped_members:
        if timezone == sender_tz:
            source_group = group
        else:
            other_groups.append((timezone, group))

    source_label = _join_city_labels(source_group, sender_city or sender_tz)
    source_flag = source_group[0].get("flag", sender_flag) if source_group else sender_flag

    rows = [
        {
            "displayed_time": normalize_time(original_time),
            "label": source_label,
            "flag": source_flag,
            "group": source_group,
        }
    ]

    for timezone, group in other_groups:
        try:
            converted_time, day_shift = convert_time(original_time, sender_tz, timezone)
        except Exception as exc:
            logger.error(f"Format group conversion failed for '{original_time}': {exc}")
            continue

        rows.append(
            {
                "displayed_time": _format_time_with_shift(converted_time, day_shift),
                "label": _join_city_labels(group, timezone),
                "flag": group[0].get("flag", ""),
                "group": group,
            }
        )

    return rows


def format_single_point_line(
    original_time: str,
    sender_city: str,
    sender_tz: str,
    sender_flag: str,
    members: list[dict],
    event_title: str = "",
    ambiguous_prefix: str = "",
) -> str:
    """Format one conversion block for a single time point."""
    show_usernames = get_show_usernames()
    rows = _build_conversion_rows(
        original_time=original_time,
        sender_city=sender_city,
        sender_tz=sender_tz,
        sender_flag=sender_flag,
        members=members,
    )

    lines = []
    if event_title and get_show_event_title():
        lines.append(event_title)

    for index, row in enumerate(rows):
        lines.append(
            _render_row(
                displayed_time=row["displayed_time"],
                label=row["label"],
                flag=row["flag"],
                group=row["group"],
                show_usernames=show_usernames,
                prefix=ambiguous_prefix if index == 0 else "",
            )
        )

    return "\n".join(lines)


def format_single_point_sentence(
    original_time: str,
    sender_city: str,
    sender_tz: str,
    sender_flag: str,
    members: list[dict],
    event_title: str = "",
    ambiguous_prefix: str = "",
) -> str:
    """Format one conversion block as a single compact sentence without flags."""
    rows = _build_conversion_rows(
        original_time=original_time,
        sender_city=sender_city,
        sender_tz=sender_tz,
        sender_flag=sender_flag,
        members=members,
    )
    if not rows:
        return ""

    lines = []
    if event_title and get_show_event_title():
        lines.append(event_title)

    sentence = "It is " + ", ".join(
        f"{row['displayed_time']} {row['label']}" for row in rows
    )
    if ambiguous_prefix:
        sentence = f"{ambiguous_prefix} {sentence}"
    lines.append(sentence)
    return "\n".join(lines)


def format_multi_conversion(conversions: list[dict], members: list[dict], sender_name: str = "") -> str:
    """Format one atomic reply containing one or more time blocks."""
    response_style = get_response_style()
    point_lines = []
    for conversion in conversions:
        ambiguous_prefix = "" if conversion.get("am_pm_clear", True) else "AM/PM🤔"
        if response_style == "inline_sentence":
            line = format_single_point_sentence(
                conversion["original_time"],
                conversion["source_city"],
                conversion["source_tz"],
                conversion["source_flag"],
                members,
                event_title=conversion.get("event_title", ""),
                ambiguous_prefix=ambiguous_prefix,
            )
        else:
            line = format_single_point_line(
                conversion["original_time"],
                conversion["source_city"],
                conversion["source_tz"],
                conversion["source_flag"],
                members,
                event_title=conversion.get("event_title", ""),
                ambiguous_prefix=ambiguous_prefix,
            )
        if line:
            point_lines.append(line)
    return "\n\n".join(point_lines)


def format_conversion_reply(
    original_time: str,
    sender_city: str,
    sender_tz: str,
    sender_flag: str,
    members: list[dict],
    sender_name: str = "",
) -> str:
    """Format a single-point conversion reply.

    Kept as a convenience wrapper for tests and any external single-point callers.
    """
    conversions = [
        {
            "original_time": original_time,
            "source_city": sender_city,
            "source_tz": sender_tz,
            "source_flag": sender_flag,
        }
    ]
    return format_multi_conversion(conversions, members, sender_name)
