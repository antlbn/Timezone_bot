import os
import yaml
import logging
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv
from core.domain.value_objects import BotSettings, LLMConfig, LLMModelConfig, LoggingConfig
from core.domain.enums import ResponseStyle
from adapters.inbound.telegram.config import TelegramConfig
from config_schema import YamlConfig

logger = logging.getLogger(__name__)

@dataclass
class AppConfig:
    tg_token: str | None
    dc_token: str | None
    logging: LoggingConfig
    llm: LLMConfig
    log_prompts: bool
    bot: BotSettings
    telegram: TelegramConfig

def build_settings(config: YamlConfig) -> BotSettings:
    style = (
        ResponseStyle.INLINE
        if config.bot.response_style == "inline_sentence"
        else ResponseStyle.BLOCK
    )

    return BotSettings(
        show_usernames=config.bot.show_usernames,
        show_event_title=config.bot.show_event_title,
        response_style=style,
        max_age_fresh_secs=config.bot.max_age_fresh_secs,
        max_message_hard_skip_chars=config.event_detection.max_message_hard_skip_chars,
        onboarding_cooldown_secs=config.bot.onboarding_cooldown_secs,
        onboarding_pending_ttl_secs=config.bot.onboarding_pending_ttl_secs,
    )

def build_tg_config(config: YamlConfig) -> TelegramConfig:
    return TelegramConfig(
        delete_delay=config.bot.group_auto_delete_delay_secs,
    )


def build_logging_config(config: YamlConfig) -> LoggingConfig:
    return LoggingConfig(
        level=config.logging.level.upper(),
    )

def load_config() -> AppConfig:
    load_dotenv()
    
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    dc_token = os.getenv("DISCORD_BOT_TOKEN")

    # YAML Setup
    config_path = Path("configuration.yaml")
    if not config_path.exists():
        logger.warning(f"Config file {config_path} not found. Using defaults.")
        raw_config_data: object = {}
    else:
        with open(config_path, "r") as f:
            raw_config_data = yaml.safe_load(f) or {}
    yaml_config = YamlConfig.model_validate(raw_config_data)
    
    primary_llm = LLMModelConfig(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        model=os.getenv("LLM_MODEL", "gemini-3-flash-lite-preview"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
    )
    fallback_llm = None
    if os.getenv("LLM_FALLBACK_API_KEY"):
        fallback_llm = LLMModelConfig(
            api_key=os.getenv("LLM_FALLBACK_API_KEY"),
            base_url=os.getenv("LLM_FALLBACK_BASE_URL"),
            model=os.getenv("LLM_FALLBACK_MODEL", "llama-3.1-8b-instant"),
            temperature=float(os.getenv("LLM_FALLBACK_TEMPERATURE", "0.0")),
        )
    llm_config = LLMConfig(primary=primary_llm, fallback=fallback_llm)
            
    return AppConfig(
        tg_token=tg_token,
        dc_token=dc_token,
        logging=build_logging_config(yaml_config),
        llm=llm_config,
        log_prompts=yaml_config.event_detection.log_prompts,
        bot=build_settings(yaml_config),
        telegram=build_tg_config(yaml_config)
    )
