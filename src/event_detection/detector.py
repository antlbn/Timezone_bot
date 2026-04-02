"""
detector.py — Simplified JSON-based Event Detection

Architecture:
  1. Build user-turn content (CURRENT MESSAGE only).
  2. Query LLM with JSON output formatting.
  3. Return structured detection output to the bot logic.
"""

import json
import os
import re
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
_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _strip_json_fences(raw: str) -> str:
    """Allow tolerant parsing when a model wraps JSON in a fenced code block."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[^\n]*\n", "", text, count=1)
        text = re.sub(r"\n```$", "", text).strip()
    return text


def _is_valid_time_string(value: Any) -> bool:
    return isinstance(value, str) and bool(_TIME_PATTERN.fullmatch(value))


def _normalize_point(point: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize the runtime schema into the internal shape and drop invalid points."""
    time_value = point.get("time")
    tz_city = point.get("tz_city")
    event_title = point.get("event_title")
    am_pm_clear = point.get("am_pm_clear")

    if not _is_valid_time_string(time_value):
        return None
    if tz_city is not None and not isinstance(tz_city, str):
        return None
    if event_title is not None and not isinstance(event_title, str):
        return None
    if not isinstance(am_pm_clear, bool):
        return None

    return {
        "time": time_value,
        "tz_city": tz_city,
        "event_title": event_title,
        "am_pm_clear": am_pm_clear,
    }


def _parse_detection_payload(raw: str) -> tuple[bool, list[dict[str, Any]]]:
    """Parse and validate the LLM payload. Invalid payloads fail safe to silence."""
    parsed = json.loads(_strip_json_fences(raw))
    if not isinstance(parsed, dict):
        raise ValueError("LLM payload must be a JSON object")

    time_mentioned = parsed.get("time_mentioned")
    points = parsed.get("points")
    if not isinstance(time_mentioned, bool):
        raise ValueError("LLM payload missing boolean time_mentioned")
    if not isinstance(points, list):
        raise ValueError("LLM payload missing list points")

    normalized_points: list[dict[str, Any]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        normalized = _normalize_point(point)
        if normalized is not None:
            normalized_points.append(normalized)

    if time_mentioned and not normalized_points:
        return False, []

    return time_mentioned and bool(normalized_points), normalized_points


def _resolve_api_key(preferred_env: str | None) -> str | None:
    """
    Resolve an API key from config-driven env names, while keeping backward-
    compatible fallbacks for existing local setups.
    """
    candidate_names: list[str] = []
    if preferred_env:
        candidate_names.append(preferred_env)
    candidate_names.extend(
        [
            "LLM_API_KEY",
            "LLM_FALLBACK_API_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "OPENAI_API_KEY",
        ]
    )

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
    time_mentioned = False
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
            time_mentioned, result_points = _parse_detection_payload(raw)

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
        "time_mentioned": time_mentioned,
        "event": time_mentioned,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "time": [p.get("time", "") for p in result_points],
        "tz_city": [p.get("tz_city") for p in result_points],
        "event_title": [p.get("event_title") for p in result_points],
        "am_pm_clear": [p.get("am_pm_clear") for p in result_points],
        "points": result_points,
    }
