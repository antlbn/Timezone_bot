"""
Configuration loader.
Loads configuration.yaml and .env file.
"""

import os
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
import yaml

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Load configuration.yaml
CONFIG_PATH = PROJECT_ROOT / "configuration.yaml"


def load_config() -> dict:
    """Load and return configuration from yaml file."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def get_config() -> dict:
    """Get cached configuration."""
    return load_config()


def reload_config() -> dict:
    """Reload configuration from disk and clear dependent runtime caches."""
    get_config.cache_clear()

    try:
        from src.event_detection.detector import clear_runtime_caches
    except Exception:
        clear_runtime_caches = None

    if clear_runtime_caches is not None:
        clear_runtime_caches()

    return get_config()


# Quick access
def get_telegram_token() -> str | None:
    """Get Telegram bot token from environment. Returns None if not set."""
    return os.getenv("TELEGRAM_TOKEN")


def get_log_level() -> str:
    """Get logging level from config."""
    return get_config().get("logging", {}).get("level", "INFO")


def get_llm_settings() -> dict:
    """Get LLM settings from config."""
    return get_config().get("llm", {})


def get_bot_settings() -> dict:
    """Get bot settings from config."""
    return get_config().get("bot", {})


def get_event_detection_settings() -> dict:
    """Get event detection settings from config."""
    return get_config().get("event_detection", {})


def get_show_usernames() -> bool:
    """Check if usernames or display names should be shown in replies."""
    return get_bot_settings().get("show_usernames", False)


def get_show_event_title() -> bool:
    """Check if event titles should be shown in replies."""
    return get_bot_settings().get("show_event_title", False)


def get_response_style() -> str:
    """Get reply rendering style."""
    return get_bot_settings().get("response_style", "block")


def get_reply_to_original_message() -> bool:
    """Check if bot responses should be sent as direct replies."""
    return get_bot_settings().get("reply_to_original_message", False)


def get_settings_cleanup_timeout() -> int:
    """Get timeout in seconds for auto-cleaning settings dialogs (0 to disable)."""
    return get_bot_settings().get("settings_cleanup_timeout_seconds", 10)


def get_max_message_age() -> int:
    """Get max message age in seconds from config."""
    return get_event_detection_settings().get("max_message_age_seconds", 20)


def get_max_message_hard_skip() -> int:
    """Read hard skip limit for long messages."""
    return get_event_detection_settings().get("max_message_hard_skip_chars", 2000)


def get_inactive_user_retention_days() -> int:
    """Read inactivity retention period for users."""
    return get_config().get("storage", {}).get("inactive_user_retention_days", 30)


def get_data_retention_days() -> int:
    """Backward-compatible alias for user data retention period."""
    return get_inactive_user_retention_days()


def get_onboarding_timeout() -> int:
    """Get onboarding timeout in seconds from config."""
    return get_event_detection_settings().get("onboarding_timeout_seconds", 60)


def get_dm_onboarding_cooldown() -> int:
    """Get cooldown before re-prompting a user who ignored/abandoned DM onboarding."""
    return get_event_detection_settings().get("dm_onboarding_cooldown_seconds", 600)


def get_log_llm_prompts() -> bool:
    """Whether to log the full current-message LLM prompts for debugging."""
    return get_event_detection_settings().get("log_prompts", False)


def get_llm_model() -> str:
    """Get LLM model id from config or environment."""
    return get_llm_settings().get("model") or os.getenv("LLM_MODEL", "gpt-5")


def get_llm_temperature() -> float:
    """Get LLM temperature from config."""
    return float(get_llm_settings().get("temperature", 0.1))


def get_llm_base_url() -> str | None:
    """Get primary LLM base URL, preferring the canonical env var."""
    return os.getenv("LLM_BASE_URL") or get_llm_settings().get("base_url")


def get_llm_fallback_base_url() -> str | None:
    """Get fallback LLM base URL, preferring the canonical env var."""
    fallback_cfg = get_llm_settings().get("fallback", {})
    return os.getenv("LLM_FALLBACK_BASE_URL") or fallback_cfg.get("base_url") or get_llm_base_url()


def get_llm_api_key_env() -> str | None:
    """Get optional env var name for the primary LLM API key."""
    return get_llm_settings().get("api_key_env")
