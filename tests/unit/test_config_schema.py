import pytest
from pydantic import ValidationError

from config import build_logging_config, build_settings, build_tg_config
from config_schema import YamlConfig
from core.domain.enums import ResponseStyle


def test_yaml_config_builds_domain_settings():
    yaml_config = YamlConfig.model_validate(
        {
            "logging": {"level": "debug"},
            "bot": {
                "show_usernames": True,
                "show_event_title": False,
                "response_style": "inline_sentence",
                "max_age_fresh_secs": 10,
                "onboarding_cooldown_secs": 20,
                "onboarding_pending_ttl_secs": 30,
                "group_auto_delete_delay_secs": 40,
            },
            "event_detection": {
                "log_prompts": True,
                "max_message_hard_skip_chars": 1234,
            },
        }
    )

    settings = build_settings(yaml_config)
    logging_config = build_logging_config(yaml_config)
    telegram_config = build_tg_config(yaml_config)

    assert settings.response_style is ResponseStyle.INLINE
    assert settings.max_message_hard_skip_chars == 1234
    assert logging_config.level == "DEBUG"
    assert telegram_config.delete_delay == 40


def test_yaml_config_rejects_unknown_top_level_sections():
    with pytest.raises(ValidationError):
        YamlConfig.model_validate({"unknown": {}})
