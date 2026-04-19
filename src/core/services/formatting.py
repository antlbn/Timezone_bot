from collections import defaultdict
from core.domain.value_objects import TimePoint, UserProfile
from core.services.conversion import convert_time, get_utc_offset, parse_time
from core.domain.enums import ResponseStyle


def normalize_time(time_str: str) -> str:
    t = parse_time(time_str)
    if t:
        return t.strftime("%H:%M")
    return time_str


def _format_time_with_shift(time_str: str, day_shift: int) -> str:
    normalized = normalize_time(time_str)
    if day_shift == 1:
        return f"{normalized}⁺¹"
    if day_shift == -1:
        return f"{normalized}⁻¹"
    return normalized


def _member_name(member: UserProfile) -> str:
    if member.username:
        return f"@{member.username}"
    return f"@{member.user_id}"


def _format_names(group: list[UserProfile], show_usernames: bool) -> str:
    if not show_usernames:
        return ""
    names = [_member_name(m) for m in group]
    if not names:
        return ""
    if len(names) <= 2:
        return ", ".join(names)
    return f"{names[0]}, {names[1]}, +{len(names) - 2} more"


def _group_members_by_timezone(members: list[UserProfile]) -> list[tuple[str, list[UserProfile]]]:
    tz_groups = defaultdict(list)
    for m in members:
        if m.timezone:
            tz_groups[m.timezone].append(m)
    return sorted(tz_groups.items(), key=lambda item: get_utc_offset(item[0]))


def _join_city_labels(group: list[UserProfile], fallback_label: str) -> str:
    labels = []
    for m in group:
        label = m.city or m.timezone
        if label and label not in labels:
            labels.append(label)
    if not labels:
        return fallback_label
    return ", ".join(labels)


def _build_conversion_rows(
    original_time: str,
    source_tz: str,
    source_label: str,
    source_flag: str,
    members: list[UserProfile],
) -> list[dict]:
    """Build the list of display rows: source first (at source_tz), then all other
    member timezones sorted by UTC offset.

    source_tz, source_label, source_flag are resolved by the caller based on
    whether tz_resolved or sender.timezone is the reference point.
    """
    grouped_members = _group_members_by_timezone(members)

    source_group: list[UserProfile] = []
    other_groups: list[tuple[str, list[UserProfile]]] = []

    for tz, group in grouped_members:
        if tz == source_tz:
            source_group = group
        else:
            other_groups.append((tz, group))

    # Use a flag found in the source member group as fallback
    if not source_flag and source_group and source_group[0].flag:
        source_flag = source_group[0].flag

    rows = [{
        "displayed_time": normalize_time(original_time),
        "label": source_label,
        "flag": source_flag,
        "group": source_group,
    }]

    for tz, group in other_groups:
        converted_time, day_shift = convert_time(original_time, source_tz, tz)
        rows.append({
            "displayed_time": _format_time_with_shift(converted_time, day_shift),
            "label": _join_city_labels(group, tz),
            "flag": group[0].flag or "",
            "group": group,
        })

    return rows


def _resolve_source(
    point: TimePoint,
    sender: UserProfile | None,
) -> tuple[str, str, str] | None:
    """Return (source_tz, source_label, source_flag) or None if no source is available.

    Priority:
      1. point.tz_resolved — explicit timezone referenced in the message ("по Лондону")
      2. sender.timezone   — sender's configured timezone

    When tz_resolved is present it wins regardless of sender timezone.
    If sender also has a timezone, they appear as a regular member row (already in ctx.members).
    """
    if point.tz_resolved:
        return (
            point.tz_resolved,
            point.tz_city or point.tz_resolved,
            "",  # flag will be resolved from members in _build_conversion_rows
        )
    if sender and sender.timezone:
        return (
            sender.timezone,
            sender.city or sender.timezone,
            sender.flag or "",
        )
    return None


def format_single_point(
    point: TimePoint,
    sender: UserProfile | None,
    members: list[UserProfile],
    response_style: ResponseStyle,
    show_usernames: bool,
    show_event_title: bool,
) -> str:
    source = _resolve_source(point, sender)
    if source is None:
        return ""  # No reference timezone — nothing to format

    source_tz, source_label, source_flag = source
    rows = _build_conversion_rows(point.time, source_tz, source_label, source_flag, members)

    ambiguous_prefix = "" if point.am_pm_clear else "AM/PM?"
    title = point.event_title if point.event_title and show_event_title else ""

    if response_style == ResponseStyle.INLINE:
        row_text = ", ".join(f"{row['displayed_time']} {row['label']}" for row in rows)
        if ambiguous_prefix:
            row_text = f"{ambiguous_prefix} {row_text}"
        if title:
            return f"{title}\n{row_text}"
        return row_text

    # Block format
    lines = []
    if title:
        lines.append(title)

    for i, row in enumerate(rows):
        parts = [row["displayed_time"], row["label"]]
        if row["flag"]:
            parts.append(row["flag"])

        line = " ".join(parts)
        if i == 0 and ambiguous_prefix:
            line = f"{ambiguous_prefix} {line}"

        names_str = _format_names(row["group"], show_usernames)
        if names_str:
            line = f"{line} {names_str}"

        lines.append(line)

    return "\n".join(lines)


def format_multi_conversion(
    points: tuple[TimePoint, ...],
    sender: UserProfile | None,
    members: list[UserProfile],
    response_style: ResponseStyle = ResponseStyle.BLOCK,
    show_usernames: bool = False,
    show_event_title: bool = False,
) -> str:
    if not points:
        return ""

    blocks = [
        block for point in points
        if (block := format_single_point(point, sender, members, response_style, show_usernames, show_event_title))
    ]

    if not blocks:
        return ""

    if response_style == ResponseStyle.INLINE:
        res = "\n".join(blocks)
        return f"It is\n{res}" if len(blocks) > 1 else f"It is {res}"

    return "\n\n".join(blocks)
