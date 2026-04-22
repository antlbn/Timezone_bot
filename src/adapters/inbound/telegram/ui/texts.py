def get_help_text() -> str:
    return (
        "<b>Timezone Bot Help</b>\n\n"
        "Personal commands:\n"
        "• /tb_me — show your current timezone\n"
        "• /tb_settz — set or change your timezone\n"
        "• /tb_decline — stop the bot and ignore me\n\n"
        "Group commands:\n"
        "• /tb_members — list tracked members in the current chat\n"
        "• /tb_deletemember [number] — remove a member from the list\n\n"
        "Mention a time in a group chat and I'll convert it for known members automatically."
    )

def get_tz_not_set_text() -> str:
    return "Your timezone is not set yet. Use /tb_settz."

def get_group_only_command_text() -> str:
    return "This command only works in groups."

def get_no_members_text(is_group: bool = True) -> str:
    if is_group:
        return "No members registered here yet. Use /tb_settz in private chat."
    return "No members registered here yet."

def get_delete_member_usage_text(members_list: str) -> str:
    return f"{members_list}\n\nTo remove a member, use: <code>/tb_deletemember [number]</code>"

def get_member_removed_text(name: str) -> str:
    return f"✅ Removed <b>{name}</b> from this chat's list."

def get_invalid_number_text() -> str:
    return "❌ Invalid number. Please use a number from the list."

def get_decline_confirmation_text() -> str:
    return "Got it! I won't ask you again. Use /tb_settz if you change your mind."

def get_not_your_button_text() -> str:
    return "This button is not for you! 😊"

def get_city_prompt_text() -> str:
    return (
        "Great! Tell me your city so I can show your local time to others.\n"
        "\n"
        "💡 Write city: e.g. <code>Paris</code> for France, or specify <code>Paris, Texas</code> for USA."
    )

def get_timezone_removed_text() -> str:
    return "🗑️ Your timezone has been removed. I'll no longer convert times for you."

def get_privacy_text() -> str:
    return (
        "Data is stored locally and used only for time conversion. "
        "User profiles are automatically deleted after 30 days of inactivity."
    )

def get_main_settings_text() -> str:
    return "<b>Main Settings</b>\nManage your timezone and preferences here:"

def get_legacy_callback_text() -> str:
    return (
        "This button belongs to an older version of the bot and is no longer active. "
        "Please use /tb_settz to get a new menu."
    )

def get_wrong_user_link_text() -> str:
    return "This setup link belongs to another user."

def get_already_set_text(city: str, flag: str | None, timezone: str) -> str:
    flag_str = f" {flag}" if flag else ""
    return (
        f"✅ Your timezone is set to: <b>{city}{flag_str}</b> ({timezone})\n"
        "\nYou can manage your settings here:"
    )

def get_onboarding_greeting_text(name: str) -> str:
    return (
        f"👋 Hi {name}!\n\n"
        "I'm a bot that converts times for chat members across different cities and time zones. "
        "To show your local time to others, I need to know your city.\n\n"
        "Ready? Tap <b>Set my city</b> below 👇"
    )

def get_city_not_found_text(city: str) -> str:
    return (
        f"Could not find city «{city}» 🤔\n"
        "Try writing in English or use /tb_decline to skip."
    )

def get_completion_text(timezone_name: str, flag: str | None) -> str:
    flag_str = f" {flag}" if flag else ""
    return (
        f"✅ Set to: <b>{timezone_name}</b>{flag_str}\n\n"
        "From now on, I will automatically convert time for you!"
    )

def get_onboarding_prompt_text(author_name: str) -> str:
    return (
        f"👋 <b>{author_name}</b>, to convert your time correctly, "
        f"please specify your city."
    )
