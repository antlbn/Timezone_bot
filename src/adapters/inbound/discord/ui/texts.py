def get_help_text() -> str:
    return (
        "I detect time mentions and convert them for your chat members automatically!\n"
        "Use `/tb_settz` to set your timezone."
    )

def get_tz_not_set_text() -> str:
    return "Your timezone is not set yet. Use `/tb_settz`."

def get_server_only_text() -> str:
    return "This command only works in servers."

def get_no_members_text() -> str:
    return "No members registered here yet. Use `/tb_settz`."

def get_decline_confirmation_text() -> str:
    return "Got it! I won't bother you again. Use `/tb_settz` if you change your mind."

def get_not_your_button_text() -> str:
    return "❌ This button is not for you!"

def get_city_not_found_text(city: str) -> str:
    return f"❌ Could not resolve city: **{city}**"

def get_completion_text(timezone_name: str, city: str, flag: str | None) -> str:
    flag_str = f" {flag}" if flag else ""
    return f"✅ Timezone set to **{timezone_name}** ({city}{flag_str})"

def get_onboarding_prompt_text(name: str) -> str:
    return (
        f"👋 **{name}**, to convert your time correctly, "
        f"please specify your city."
    )

def get_onboarding_embed_title(name: str) -> str:
    return f"👋 Welcome to Timezone Bot, {name}!"

def get_onboarding_embed_description() -> str:
    return (
        "I've detected a time mention, but I don't know your timezone yet.\n\n"
        "Tap the button below to quickly set it up! (Only you will see the next steps)"
    )

