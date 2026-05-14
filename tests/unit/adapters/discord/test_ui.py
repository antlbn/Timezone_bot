from core.domain.enums import Platform
from core.domain.value_objects import UserProfile
from adapters.inbound.discord import ui

def test_help_text_mentions_settz() -> None:
    text = ui.get_help_text()
    assert "/tb_settz" in text
    assert "time mentions" in text

def test_format_user_timezone_discord_style() -> None:
    user = UserProfile(
        user_id=1,
        platform=Platform.DISCORD,
        city="Paris",
        timezone="Europe/Paris",
        flag="🇫🇷",
    )
    
    formatted = ui.format_user_timezone(user)
    assert "Paris" in formatted
    assert "🇫🇷" in formatted
    assert "Europe/Paris" in formatted

def test_format_chat_members_discord_style() -> None:
    members = [
        UserProfile(
            user_id=1,
            platform=Platform.DISCORD,
            username="claire",
            city="Berlin",
            timezone="Europe/Berlin",
            flag="🇩🇪",
        ),
        UserProfile(
            user_id=2,
            platform=Platform.DISCORD,
            username="dexter",
            city=None,
            timezone=None,
        )
    ]
    
    text = ui.format_chat_members(members)
    
    assert "**Server members:**" in text
    assert "1. Berlin 🇩🇪 (@claire)" in text
    assert "2. Unknown (@dexter) — timezone not set" in text

def test_onboarding_embed_texts() -> None:
    title = ui.get_onboarding_embed_title("Dexter")
    desc = ui.get_onboarding_embed_description()
    
    assert "Dexter" in title
    assert "detected a time mention" in desc
    assert "quickly set it up" in desc

def test_decline_confirmation_text() -> None:
    text = ui.get_decline_confirmation_text()
    assert "won't bother you again" in text
    assert "/tb_settz" in text
