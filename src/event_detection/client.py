import os
from openai import AsyncOpenAI
from src.logger import get_logger
from src.config import get_llm_base_url, get_llm_model as get_configured_llm_model

logger = get_logger()

# By default, point to Ollama running locally.
# This makes the bot completely vendor-agnostic (local/OpenAI/Grok/etc.)
_client = None


def get_llm_client() -> AsyncOpenAI:
    """
    Returns a configured, singleton AsyncOpenAI client instance.
    Uses LLM_BASE_URL and LLM_API_KEY from environment.
    """
    global _client
    if _client is None:
        base_url = get_llm_base_url()
        api_key = os.getenv("GEMINI_API_KEY")

        _client = AsyncOpenAI(base_url=base_url, api_key=api_key, http_client=None)
        logger.info(f"Initialized LLM client with base_url: {base_url}")

    return _client


def get_llm_model() -> str:
    """Returns the configured model name, e.g. 'llama3' or 'gpt-4o-mini'."""
    return get_configured_llm_model()
