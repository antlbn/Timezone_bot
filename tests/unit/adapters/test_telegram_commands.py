from core.domain.enums import Platform
from core.domain.value_objects import UserProfile

from adapters.inbound.telegram.commands_handler import (
    _build_help_text,
    _build_private_setup_prompt,
    _format_chat_members,
    _format_user_timezone,
)


def test_private_help_text_contains_personal_and_group_commands() -> None:
    text = _build_help_text("private")

    assert "/tb_me" in text
    assert "/tb_settz" in text
    assert "/tb_members" in text


def test_group_help_text_does_not_advertise_private_only_me_command() -> None:
    text = _build_help_text("group")

    assert "/tb_members" in text
    assert "• /tb_me " not in text


def test_private_setup_prompt_mentions_city_and_skip() -> None:
    text = _build_private_setup_prompt()

    assert "city" in text.lower()
    assert "/skip" in text


def test_format_user_timezone_includes_flag_when_present() -> None:
    user = UserProfile(
        user_id=1,
        platform=Platform.TELEGRAM,
        city="Vienna",
        timezone="Europe/Vienna",
        flag="🇦🇹",
    )

    assert _format_user_timezone(user) == "Vienna 🇦🇹 (Europe/Vienna)"


def test_format_chat_members_uses_html_heading_and_usernames() -> None:
    members = [
        UserProfile(
            user_id=1,
            platform=Platform.TELEGRAM,
            username="alice",
            city="Vienna",
            timezone="Europe/Vienna",
            flag="🇦🇹",
        )
    ]

    text = _format_chat_members(members)

    assert "<b>Chat members:</b>" in text
    assert "Vienna 🇦🇹 (@alice)" in text


def test_format_chat_members_marks_missing_timezone() -> None:
    members = [
        UserProfile(
            user_id=2,
            platform=Platform.TELEGRAM,
            username="bob",
            city="Unknown",
            timezone=None,
        )
    ]

    text = _format_chat_members(members)

    assert "timezone not set" in text
