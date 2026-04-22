import pytest
from adapters.inbound.telegram.common import parse_onboarding_payload, OnboardingStartContext

def test_parse_onboarding_payload_simple() -> None:
    result = parse_onboarding_payload("onboard_123")
    assert result == OnboardingStartContext(target_user_id=123, source_chat_id=None)

def test_parse_onboarding_payload_with_chat() -> None:
    result = parse_onboarding_payload("onboard_123_-456")
    assert result == OnboardingStartContext(target_user_id=123, source_chat_id="-456")

def test_parse_onboarding_payload_with_complex_ids() -> None:
    # If the user ID contains underscores (which it doesn't in Telegram, but we support it for robustness),
    # the last underscore is the separator for the chat ID.
    result = parse_onboarding_payload("onboard_123_456_789")
    assert result == OnboardingStartContext(target_user_id=123456, source_chat_id="789")

def test_parse_onboarding_payload_invalid() -> None:
    assert parse_onboarding_payload(None) is None
    assert parse_onboarding_payload("") is None
    assert parse_onboarding_payload("invalid") is None
    assert parse_onboarding_payload("onboard_") is None
    assert parse_onboarding_payload("onboard_abc") is None
