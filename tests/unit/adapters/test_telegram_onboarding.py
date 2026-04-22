from adapters.inbound.telegram.onboarding_handler import (
    OnboardingStartContext,
    parse_onboarding_start_context,
)


def test_parse_onboarding_start_context_accepts_user_only_payload() -> None:
    assert parse_onboarding_start_context("onboard_42") == OnboardingStartContext(
        target_user_id=42,
        source_chat_id=None,
    )


def test_parse_onboarding_start_context_accepts_user_and_chat_payload() -> None:
    assert parse_onboarding_start_context("onboard_42_-100123") == OnboardingStartContext(
        target_user_id=42,
        source_chat_id="-100123",
    )


def test_parse_onboarding_start_context_rejects_invalid_payloads() -> None:
    assert parse_onboarding_start_context(None) is None
    assert parse_onboarding_start_context("") is None
    assert parse_onboarding_start_context("onboard") is None
    assert parse_onboarding_start_context("onboard_abc") is None
    assert parse_onboarding_start_context("onboard_42_") is None
    assert parse_onboarding_start_context("onboard_42_-") is None
    assert parse_onboarding_start_context("onboard_42_chat_extra") is None
    assert parse_onboarding_start_context("start=onboard_42") is None
