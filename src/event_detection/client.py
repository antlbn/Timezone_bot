import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

from src.config import get_bot_settings
from src.logger import get_logger

logger = get_logger()

def get_llm_model() -> str:
    """Returns the configured model name, e.g. 'llama3' or 'gpt-4o-mini'."""
    return os.getenv("LLM_MODEL", "gemini-3.1-flash-lite-preview")


@lru_cache(maxsize=1)
def get_chat_llm() -> ChatOpenAI:
    """Returns a cached ChatOpenAI client configured from env/settings."""
    settings = get_bot_settings()
    temperature = settings.get("llm", {}).get("temperature", 0.0)
    model_name = get_llm_model()
    base_url = os.getenv("LLM_BASE_URL") or None
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or "no-key"
    )

    logger.info(f"Initialized ChatOpenAI client with model={model_name}, base_url={base_url}")
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        openai_api_base=base_url,
        openai_api_key=api_key,
    )


@lru_cache(maxsize=1)
def get_bound_chat_llm() -> object:
    """Returns the cached tool-bound runnable used by the event detection graph."""
    from src.event_detection.graph import tools_list

    return get_chat_llm().bind_tools(tools_list)


def reset_llm_cache() -> None:
    """Clear cached LLM clients. Intended for tests or controlled reloads."""
    get_bound_chat_llm.cache_clear()
    get_chat_llm.cache_clear()
