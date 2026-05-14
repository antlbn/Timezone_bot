from core.domain.enums import Platform
from core.domain.value_objects import UserProfile
from adapters.inbound.telegram import ui

def test_help_text_contains_all_commands() -> None:
    text = ui.get_help_text()
    
    assert "/tb_me" in text
    assert "/tb_settz" in text
    assert "/tb_members" in text
    # /tb_help is not listed in the text itself to avoid recursion

def test_format_user_timezone_includes_flag_and_city() -> None:
    user = UserProfile(
        user_id=1,
        platform=Platform.TELEGRAM,
        city="London",
        timezone="Europe/London",
        flag="🇬🇧",
    )
    
    formatted = ui.format_user_timezone(user)
    assert "London" in formatted
    assert "🇬🇧" in formatted
    assert "Europe/London" in formatted

def test_format_chat_members_with_various_profiles() -> None:
    members = [
        UserProfile(
            user_id=1,
            platform=Platform.TELEGRAM,
            username="alice",
            city="Vienna",
            timezone="Europe/Vienna",
            flag="🇦🇹",
        ),
        UserProfile(
            user_id=2,
            platform=Platform.TELEGRAM,
            username="bob",
            city=None,
            timezone=None,
        )
    ]
    
    text = ui.format_chat_members(members)
    
    assert "<b>Chat members:</b>" in text
    assert "1. Vienna 🇦🇹 (@alice)" in text
    assert "2. Unknown (@bob) — timezone not set" in text

def test_onboarding_prompt_text_includes_name() -> None:
    text = ui.get_onboarding_prompt_text("John")
    assert "John" in text
    assert "convert your time" in text

def test_error_message_text() -> None:
    text = ui.get_error_message_text()
    assert "❌" in text
    assert "Something went wrong" in text
