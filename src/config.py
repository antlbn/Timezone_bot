import os
import yaml
import logging
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv
from core.domain.value_objects import BotSettings, LLMConfig, LLMModelConfig
from core.domain.enums import ResponseStyle
from adapters.inbound.telegram.config import TelegramConfig

logger = logging.getLogger(__name__)

@dataclass
class AppConfig:
    tg_token: str | None
    dc_token: str | None
    llm: LLMConfig
    bot: BotSettings
    telegram: TelegramConfig

def build_settings(config_data: dict) -> BotSettings:
    bot_config = config_data.get("bot", {})
    response_style_str = bot_config.get("response_style", "block")
    style = ResponseStyle.INLINE if response_style_str.lower() == "inline_sentence" else ResponseStyle.BLOCK

    return BotSettings(
        show_usernames=bot_config.get("show_usernames", False),
        show_event_title=bot_config.get("show_event_title", True),
        response_style=style,
        max_age_fresh_secs=bot_config.get("max_age_fresh_secs", 30),
        onboarding_cooldown_secs=bot_config.get("onboarding_cooldown_secs", 3600),
        onboarding_pending_ttl_secs=bot_config.get("onboarding_pending_ttl_secs", 3600),
    )

def build_tg_config(config_data: dict) -> TelegramConfig:
    bot_config = config_data.get("bot", {})
    return TelegramConfig(
        delete_delay=bot_config.get("group_auto_delete_delay_secs", 20),
    )

def load_config() -> AppConfig:
    load_dotenv()
    
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    dc_token = os.getenv("DISCORD_BOT_TOKEN")
    
    # LLM Setup
    primary_llm = LLMModelConfig(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        model=os.getenv("LLM_MODEL", "gemini-3-flash-lite-preview")
    )
    fallback_llm = None
    if os.getenv("LLM_FALLBACK_API_KEY"):
        fallback_llm = LLMModelConfig(
            api_key=os.getenv("LLM_FALLBACK_API_KEY"),
            base_url=os.getenv("LLM_FALLBACK_BASE_URL"),
            model=os.getenv("LLM_FALLBACK_MODEL", "llama-3.1-8b-instant")
        )
    llm_config = LLMConfig(primary=primary_llm, fallback=fallback_llm)
    
    # YAML Setup
    config_path = Path("configuration.yaml")
    if not config_path.exists():
        logger.warning(f"Config file {config_path} not found. Using defaults.")
        config_data = {}
    else:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f) or {}
            
    return AppConfig(
        tg_token=tg_token,
        dc_token=dc_token,
        llm=llm_config,
        bot=build_settings(config_data),
        telegram=build_tg_config(config_data)
    )
