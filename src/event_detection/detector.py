"""
detector.py — Simplified JSON-based Event Detection

Architecture:
  1. Build user-turn content (CURRENT MESSAGE only).
  2. Query LLM with JSON output formatting.
  3. Respond to the chat if an event is detected.
"""

import json
import logging
from typing import Any, Callable, Awaitable

import os
from langchain_openai import ChatOpenAI

from src.logger import get_logger
from src.event_detection.client import get_llm_model
from src.event_detection.prompts import get_system_prompt
from src.config import (
    get_config,
    get_log_llm_prompts,
    get_llm_base_url,
    get_llm_temperature,
)

logger = get_logger()


def _normalize_point(point: dict) -> dict:
    """Normalize old and new point schemas into the current internal shape."""
    return {
        "time": point.get("time"),
        "city": point.get("city"),
        "event_title": point.get("event_title", point.get("event_type")),
    }


def _build_llm_attempts() -> list[dict]:
    """Build primary and optional fallback LLM configurations."""
    cfg = get_config()
    llm_cfg = cfg.get("llm", {})
    attempts = [
        {
            "name": "primary",
            "model": llm_cfg.get("model") or get_llm_model(),
            "base_url": llm_cfg.get("base_url") or get_llm_base_url(),
            "temperature": float(llm_cfg.get("temperature", get_llm_temperature())),
            "api_key": os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY"),
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
                "api_key": os.getenv(fallback.get("api_key_env", "")) if fallback.get("api_key_env") else attempts[0]["api_key"],
            }
        )

    return attempts


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


# ─────────────────────────────────────────────────────────────────────────────
# Reply formatter helper 
# ─────────────────────────────────────────────────────────────────────────────

async def _build_reply(
    points: list[dict],
    sender_id: str,
    sender_name: str,
    sender_db: dict,
    platform: str,
    chat_id: str,
    ctx_logger: Any,
) -> str | None:
    """Build the formatted conversion reply string, or None if no members."""
    from src.storage import storage
    from src import formatter

    members = await storage.get_chat_members(chat_id, platform=platform)
    if not members:
        ctx_logger.warning(f"[chat:{chat_id}] No members in DB, skipping reply.")
        return None

    conversions = []
    for point in points:
        time_str = point.get("time")
        city_override = point.get("city")

        if city_override:
            from src.geo import async_get_timezone_by_city
            geo_result = await async_get_timezone_by_city(city_override)
            if geo_result and not geo_result.get("error"):
                source_city = geo_result["city"]
                source_tz = geo_result["timezone"]
                source_flag = geo_result["flag"]
            else:
                source_city = sender_db.get("city")
                source_tz = sender_db.get("timezone")
                source_flag = sender_db.get("flag", "")
        else:
            source_city = sender_db.get("city")
            source_tz = sender_db.get("timezone")
            source_flag = sender_db.get("flag", "")

        if not source_tz:
            ctx_logger.debug(f"[chat:{chat_id}] No source TZ for point {point}, skipping.")
            continue

        conversions.append({
            "original_time": time_str,
            "source_city": source_city,
            "source_tz": source_tz,
            "source_flag": source_flag,
            "event_title": point.get("event_title"),
        })

    if not conversions:
        return None

    return formatter.format_multi_conversion(
        conversions=conversions, members=members, sender_name=sender_name
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main detect_event — LangChain agent entry point
# ─────────────────────────────────────────────────────────────────────────────

async def detect_event(
    current_msg: dict,
    snapshot: list[dict],      # Kept for signature compatibility for now
    sender_db: dict,
    send_fn: Callable[[str], Awaitable[str | None]] | None = None,
    edit_fn: Callable[[str, str], Awaitable[None]] | None = None, # Kept for signature compatibility
    platform: str = "",
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
    message_id: str | None = None
    event_detected = False

    last_error: Exception | None = None
    for attempt in _build_llm_attempts():
        try:
            ctx_logger.info(
                f"[chat:{chat_id}] LLM attempt={attempt['name']} model={attempt['model']}"
            )
            llm = ChatOpenAI(
                model=attempt["model"],
                openai_api_key=attempt["api_key"],
                base_url=attempt["base_url"],
                temperature=attempt["temperature"],
                model_kwargs={"response_format": {"type": "json_object"}},
            )
            response = await llm.ainvoke(messages)
            raw = response.content or "{}"

            parsed = json.loads(raw)
            event_detected = bool(parsed.get("event"))
            result_points = [_normalize_point(point) for point in parsed.get("points", [])]

            if not event_detected and getattr(response, "tool_calls", None):
                for tool_call in response.tool_calls:
                    if tool_call.get("name") == "publish_event":
                        event_detected = True
                        args = tool_call.get("args", {})
                        result_points = [
                            _normalize_point(point) for point in args.get("points", [])
                        ]
                        break

            if event_detected and result_points and send_fn:
                reply = await _build_reply(
                    result_points, sender_id, sender_name, sender_db, platform, chat_id, ctx_logger
                )
                if reply:
                    message_id = await send_fn(reply)
                    ctx_logger.info(
                        f"[chat:{chat_id}] sent new message (id={message_id}, points={len(result_points)})"
                    )
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
        "message_id": message_id,
    }
