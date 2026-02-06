"""
Configuration loader.
Loads configuration.yaml and .env file.
"""
import os
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

# Singleton config
_config = None

def get_config() -> dict:
    """Get cached configuration."""
    global _config
    if _config is None:
        _config = load_config()
    return _config

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

def get_capture_patterns() -> list:
    """Get regex patterns for time capture."""
    return get_config().get("capture", {}).get("patterns", [])
