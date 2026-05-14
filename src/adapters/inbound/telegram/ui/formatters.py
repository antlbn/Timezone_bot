from core.domain.value_objects import UserProfile

def format_user_timezone(user: UserProfile) -> str:
    flag = f" {user.flag}" if user.flag else ""
    city = user.city or "Unknown"
    return f"{city}{flag} ({user.timezone})"

def format_chat_members(members: list[UserProfile]) -> str:
    lines = ["<b>Chat members:</b>"]
    for i, member in enumerate(members, 1):
        flag = f" {member.flag}" if member.flag else ""
        city = member.city or "Unknown"
        username = f" (@{member.username})" if member.username else ""
        suffix = "" if member.timezone else " — timezone not set"
        lines.append(f"{i}. {city}{flag}{username}{suffix}")
    return "\n".join(lines)
