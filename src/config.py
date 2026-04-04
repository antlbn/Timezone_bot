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


def reset_config_cache() -> None:
    """Clear cached configuration. Intended for tests or controlled reloads."""
    get_config.cache_clear()


# Quick access
def get_telegram_token() -> str | None:
    """Get Telegram bot token from environment. Returns None if not set."""
    return os.getenv("TELEGRAM_TOKEN")


def get_log_level() -> str:
    """Get logging level from config."""
    return get_config().get("logging", {}).get("level", "INFO")


def get_bot_settings() -> dict:
    """Get bot settings from config."""
    return get_config().get("bot", {})


def get_settings_cleanup_timeout() -> int:
    """Get timeout in seconds for auto-cleaning settings dialogs (0 to disable)."""
    return get_config().get("bot", {}).get("settings_cleanup_timeout_seconds", 10)


def get_max_message_age() -> int:
    """Get max message age in seconds from config."""
    return get_config().get("event_detection", {}).get("max_message_age_seconds", 20)


def get_max_message_hard_skip() -> int:
    """Read hard skip limit for long messages."""
    return (
        get_config().get("event_detection", {}).get("max_message_hard_skip_chars", 2000)
    )


def get_inactive_user_retention_days() -> int:
    """Read inactivity retention period for users."""
    return get_config().get("storage", {}).get("inactive_user_retention_days", 30)


def get_dm_onboarding_cooldown() -> int:
    """Get cooldown before re-prompting a user who ignored/abandoned DM onboarding."""
    return (
        get_config()
        .get("event_detection", {})
        .get("dm_onboarding_cooldown_seconds", 600)
    )


def get_log_llm_prompts() -> bool:
    """Whether to log the full LLM prompts (including history) for debugging."""
    config = get_config()
    return config.get("event_detection_debug", {}).get(
        "log_prompts",
        config.get("event_detection", {}).get("log_prompts", False),
    )


def get_edit_in_place_enabled() -> bool:
    """Whether to edit messages in place or always republish."""
    return get_config().get("event_detection", {}).get("edit_in_place", True)

def get_republish_edited_message_after_distance() -> int:
    """Get the distance threshold after which an edited message is republished instead of silently edited."""
    return get_config().get("event_detection", {}).get("republish_edited_message_after_distance", 8)

def get_context_messages_limit() -> int:
    """Get the number of recent human messages to pass to the LLM context window."""
    return get_config().get("event_detection", {}).get("context_messages", 5)

def get_max_tokens_limit() -> int:
    """Get the token limit for the total LLM prompt context."""
    return get_config().get("event_detection", {}).get("max_tokens", 2500)


def get_max_message_length_limit() -> int:
    """Get the soft per-message truncation limit before prompt assembly."""
    return get_config().get("event_detection", {}).get("max_message_length_chars", 500)


def get_event_detection_temperature() -> float:
    """Get the configured temperature for the event-detection LLM."""
    return float(get_config().get("event_detection", {}).get("temperature", 0.0))
