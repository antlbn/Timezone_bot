"""
detector.py — Simplified JSON-based Event Detection

Architecture:
  1. Build user-turn content (CURRENT MESSAGE only).
  2. Query LLM with JSON output formatting.
  3. Return structured detection output to the bot logic.
"""

import json
import os
from functools import lru_cache
from typing import Any

from openai import AsyncOpenAI

from src.logger import get_logger
from src.event_detection.prompts import get_system_prompt
from src.config import (
    get_config,
    get_log_llm_prompts,
    get_llm_api_key_env,
    get_llm_base_url,
    get_llm_model,
    get_llm_temperature,
)

logger = get_logger()


_openai_clients: dict[tuple[str | None, str | None], AsyncOpenAI] = {}


def _strip_json_fences(raw: str) -> str:
    """Allow tolerant parsing when a model wraps JSON in a fenced code block."""
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _normalize_point(point: dict) -> dict:
    """Normalize old and new point schemas into the current internal shape."""
    return {
        "time": point.get("time"),
        "city": point.get("city"),
        "event_title": point.get("event_title"),
    }


def _resolve_api_key(preferred_env: str | None) -> str | None:
    """
    Resolve an API key from config-driven env names, while keeping backward-
    compatible fallbacks for existing local setups.
    """
    candidate_names: list[str] = []
    if preferred_env:
        candidate_names.append(preferred_env)
    candidate_names.extend(["GEMINI_API_KEY", "OPENAI_API_KEY"])

    seen = set()
    for env_name in candidate_names:
        if not env_name or env_name in seen:
            continue
        seen.add(env_name)
        value = os.getenv(env_name)
        if value:
            return value
    return None


@lru_cache(maxsize=1)
def _build_llm_attempts() -> tuple[dict, ...]:
    """Build primary and optional fallback LLM configurations."""
    cfg = get_config()
    llm_cfg = cfg.get("llm", {})
    attempts = [
        {
            "name": "primary",
            "model": llm_cfg.get("model") or get_llm_model(),
            "base_url": llm_cfg.get("base_url") or get_llm_base_url(),
            "temperature": float(llm_cfg.get("temperature", get_llm_temperature())),
            "api_key": _resolve_api_key(llm_cfg.get("api_key_env") or get_llm_api_key_env()),
        }
    ]

    fallback = llm_cfg.get("fallback")
    if fallback and fallback.get("enabled", True) and fallback.get("model"):
        attempts.append(
            {
                "name": "fallback",
                "model": fallback["model"],
                "base_url": fallback.get("base_url") or attempts[0]["base_url"],
                "temperature": float(fallback.get("temperature", attempts[0]["temperature"])),
                "api_key": _resolve_api_key(fallback.get("api_key_env")) or attempts[0]["api_key"],
            }
        )

    return tuple(attempts)


def _create_openai_client(attempt: dict) -> AsyncOpenAI:
    """Reuse OpenAI-compatible async clients across requests."""
    client_key = (attempt["base_url"], attempt["api_key"])
    client = _openai_clients.get(client_key)
    if client is None:
        client = AsyncOpenAI(
            api_key=attempt["api_key"],
            base_url=attempt["base_url"],
            http_client=None,
        )
        _openai_clients[client_key] = client
    return client


def clear_runtime_caches() -> None:
    """Clear detector-level caches used by config and test reloads."""
    _build_llm_attempts.cache_clear()
    _openai_clients.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_user_content(current_msg: dict) -> str:
    """Compose the plain-text user-turn block that goes to the LLM."""
    anchor = current_msg.get("timestamp_utc", "")
    return (
        f"CURRENT TIME (UTC): {anchor}\n"
        f"CURRENT MESSAGE:\n{current_msg.get('text', '')}"
    )


async def detect_event(
    current_msg: dict,
    chat_id: str = "",
    ctx_logger: Any = None,
) -> dict:
    if ctx_logger is None:
        ctx_logger = logger

    sender_id = current_msg.get("author_id", "")
    sender_name = current_msg.get("author_name", "Unknown")
    user_content = _build_user_content(current_msg)

    if get_log_llm_prompts():
        ctx_logger.info(f"\n🚀 [LLM PROMPT LOG MODE] 🚀\n{user_content}\n" + "-" * 42)
    else:
        ctx_logger.debug(f"LLM call | msg='{current_msg.get('text', '')[:60]}'")

    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": user_content},
    ]

    result_points: list[dict] = []
    event_detected = False
    last_error: Exception | None = None
    for attempt in _build_llm_attempts():
        try:
            ctx_logger.info(
                f"[chat:{chat_id}] LLM attempt={attempt['name']} model={attempt['model']}"
            )
            client = _create_openai_client(attempt)
            response = await client.chat.completions.create(
                model=attempt["model"],
                temperature=attempt["temperature"],
                response_format={"type": "json_object"},
                messages=messages,
            )
            raw = response.choices[0].message.content or "{}"

            parsed = json.loads(_strip_json_fences(raw))
            event_detected = bool(parsed.get("event"))
            result_points = [_normalize_point(point) for point in parsed.get("points", [])]

            break
        except Exception as exc:
            last_error = exc
            ctx_logger.error(
                f"[chat:{chat_id}] LLM attempt failed: attempt={attempt['name']} model={attempt['model']} error={exc}"
            )
            continue
    else:
        if last_error:
            ctx_logger.error(f"[chat:{chat_id}] All LLM attempts failed. last_error={last_error}")

    return {
        "event": event_detected,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "time": [p.get("time", "") for p in result_points],
        "city": [p.get("city") for p in result_points],
        "event_title": [p.get("event_title") for p in result_points],
        "points": result_points,
    }
