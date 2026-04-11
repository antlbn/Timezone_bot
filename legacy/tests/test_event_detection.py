import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import get_max_message_age
from src.event_detection import process_message


@pytest.mark.asyncio
async def test_process_message_event():
    mock_result = {
        "time_mentioned": True,
        "event": True,
        "sender_id": "456",
        "sender_name": "John",
        "time": ["15:00"],
        "tz_city": [None],
        "event_title": [None],
        "am_pm_clear": [True],
        "points": [
            {"time": "15:00", "tz_city": None, "event_title": None, "am_pm_clear": True}
        ],
    }

    with patch(
        "src.event_detection.detect_event", new_callable=AsyncMock
    ) as mock_detect:
        mock_detect.return_value = mock_result

        res = await process_message(
            message_text="Let's meet at 15:00",
            chat_id="123",
            user_id="456",
            platform="telegram",
            author_name="John",
            timestamp_utc="2026-03-05T10:00:00Z",
            sender_db={"timezone": "Europe/London", "city": "London"},
            skip_aging=True,
        )

    assert res["time_mentioned"] is True
    assert res["event"] is True
    assert res["time"] == ["15:00"]
    assert res["sender_id"] == "456"
    mock_detect.assert_called_once()


@pytest.mark.asyncio
async def test_llm_json_dispatch():
    from src.event_detection.detector import detect_event

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "time_mentioned": True,
                        "points": [
                            {
                                "time": "20:00",
                                "tz_city": "London",
                                "event_title": "созвон",
                                "am_pm_clear": True,
                            }
                        ],
                    }
                )
            )
        )
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("src.event_detection.detector.AsyncOpenAI", return_value=mock_client):
        result = await detect_event(
            current_msg={
                "author_id": "888",
                "author_name": "Boss",
                "text": "Call at 8pm London",
                "timestamp_utc": "2026-03-14T20:00:00Z",
            },
            chat_id="chat1",
        )

    assert result["time_mentioned"] is True
    assert result["time"] == ["20:00"]
    assert result["tz_city"] == ["London"]
    assert result["event_title"] == ["созвон"]


@pytest.mark.asyncio
async def test_llm_json_dispatch_strips_markdown_fences():
    from src.event_detection.detector import detect_event

    fenced_json = """```json
{"time_mentioned": true, "points": [{"time": "20:00", "tz_city": "London", "event_title": "созвон", "am_pm_clear": true}]}
```"""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=fenced_json))]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("src.event_detection.detector.AsyncOpenAI", return_value=mock_client):
        result = await detect_event(
            current_msg={
                "author_id": "888",
                "author_name": "Boss",
                "text": "Call at 8pm London",
                "timestamp_utc": "2026-03-14T20:00:00Z",
            },
            chat_id="chat1",
        )

    assert result["time_mentioned"] is True
    assert result["time"] == ["20:00"]


def test_strip_json_fences_handles_language_and_trailing_fence():
    from src.event_detection.detector import _strip_json_fences

    raw = '```json\n{"time_mentioned": true, "points": []}\n```'

    assert _strip_json_fences(raw) == '{"time_mentioned": true, "points": []}'


@pytest.mark.asyncio
async def test_llm_fallback_attempt_used(monkeypatch):
    from src.event_detection.detector import clear_runtime_caches, detect_event

    monkeypatch.setenv("LLM_API_KEY", "test-primary-key")
    monkeypatch.setenv("LLM_FALLBACK_API_KEY", "test-fallback-key")
    clear_runtime_caches()

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "time_mentioned": True,
                        "points": [
                            {
                                "time": "20:00",
                                "tz_city": "London",
                                "event_title": "созвон",
                                "am_pm_clear": True,
                            }
                        ],
                    }
                )
            )
        )
    ]

    shared_client = MagicMock()
    shared_client.chat.completions.create = AsyncMock(
        side_effect=[RuntimeError("primary down"), mock_response]
    )

    with (
        patch(
            "src.event_detection.detector.get_config",
            return_value={
                "llm": {
                    "model": "primary-model",
                    "temperature": 0.1,
                    "base_url": "https://primary.example/v1",
                    "fallback": {"enabled": True, "model": "fallback-model"},
                }
            },
        ),
        patch(
            "src.event_detection.detector.AsyncOpenAI", return_value=shared_client
        ) as mock_client_cls,
    ):
        result = await detect_event(
            current_msg={
                "author_id": "888",
                "author_name": "Boss",
                "text": "Call at 8pm London",
                "timestamp_utc": "2026-03-14T20:00:00Z",
            },
            chat_id="chat1",
        )

    assert result["time_mentioned"] is True
    assert result["event_title"] == ["созвон"]
    assert shared_client.chat.completions.create.await_count == 2
    assert mock_client_cls.call_count == 2


@pytest.mark.asyncio
async def test_process_message_builds_reply_text(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-primary-key")

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "time_mentioned": True,
                        "points": [
                            {
                                "time": "20:00",
                                "tz_city": "London",
                                "event_title": "созвон",
                                "am_pm_clear": True,
                            }
                        ],
                    }
                )
            )
        )
    ]

    primary_client = MagicMock()
    primary_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with (
        patch(
            "src.event_detection.detector.get_config",
            return_value={
                "llm": {
                    "model": "primary-model",
                    "temperature": 0.1,
                    "base_url": "https://primary.example/v1",
                    "fallback": {"enabled": True, "model": "fallback-model"},
                }
            },
        ),
        patch(
            "src.event_detection.detector.AsyncOpenAI", return_value=primary_client
        ) as mock_client_cls,
        patch(
            "src.storage.storage.get_chat_members",
            AsyncMock(
                return_value=[
                    {
                        "user_id": "888",
                        "username": "boss",
                        "timezone": "Europe/London",
                        "city": "London",
                        "flag": "🇬🇧",
                    }
                ]
            ),
        ),
    ):
        result = await process_message(
            message_text="Call at 8pm London",
            chat_id="chat1",
            user_id="888",
            platform="telegram",
            author_name="Boss",
            timestamp_utc="2026-03-14T20:00:00Z",
            sender_db={"timezone": "Europe/London", "city": "London"},
            skip_aging=True,
        )

    assert result["time_mentioned"] is True
    assert result["time"] == ["20:00"]
    assert "20:00 London" in result["reply_text"]
    assert "созвон" in result["reply_text"]
    assert mock_client_cls.call_count == 1


def test_openai_client_reused_for_same_endpoint():
    from src.event_detection.detector import _create_openai_client, clear_runtime_caches

    attempt = {
        "api_key": "test-key",
        "base_url": "https://example.invalid/v1",
    }

    with patch("src.event_detection.detector.AsyncOpenAI") as mock_client_cls:
        first = _create_openai_client(attempt)
        second = _create_openai_client(attempt)

    assert first is second
    mock_client_cls.assert_called_once_with(
        api_key="test-key",
        base_url="https://example.invalid/v1",
        http_client=None,
    )

    clear_runtime_caches()


@pytest.mark.asyncio
async def test_message_age_limit():
    max_age = get_max_message_age()
    old_time = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(seconds=max_age + 1)
    ).isoformat()

    with patch(
        "src.event_detection.detect_event", new_callable=AsyncMock
    ) as mock_detect:
        res = await process_message(
            "Old message", "chat1", "u1", "tg", "J", old_time, skip_aging=False
        )

    assert res["time_mentioned"] is False
    assert "stale" in res.get("reason", "").lower()
    mock_detect.assert_not_called()


@pytest.mark.asyncio
async def test_llm_invalid_json_fails_silent():
    from src.event_detection.detector import detect_event

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="not json"))]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("src.event_detection.detector.AsyncOpenAI", return_value=mock_client):
        result = await detect_event(
            current_msg={
                "author_id": "888",
                "author_name": "Boss",
                "text": "Call at 8pm London",
                "timestamp_utc": "2026-03-14T20:00:00Z",
            },
            chat_id="chat1",
        )

    assert result["time_mentioned"] is False
    assert result["points"] == []


@pytest.mark.asyncio
async def test_llm_invalid_time_point_dropped_but_valid_survives():
    from src.event_detection.detector import detect_event

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "time_mentioned": True,
                        "points": [
                            {
                                "time": "99:99",
                                "tz_city": "Chicago",
                                "event_title": None,
                                "am_pm_clear": True,
                            },
                            {
                                "time": "20:00",
                                "tz_city": "London",
                                "event_title": "call",
                                "am_pm_clear": True,
                            },
                        ],
                    }
                )
            )
        )
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("src.event_detection.detector.AsyncOpenAI", return_value=mock_client):
        result = await detect_event(
            current_msg={
                "author_id": "888",
                "author_name": "Boss",
                "text": "Call at 8pm London",
                "timestamp_utc": "2026-03-14T20:00:00Z",
            },
            chat_id="chat1",
        )

    assert result["time_mentioned"] is True
    assert result["time"] == ["20:00"]
    assert result["tz_city"] == ["London"]


@pytest.mark.asyncio
async def test_llm_missing_am_pm_clear_fails_silent():
    from src.event_detection.detector import detect_event

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "time_mentioned": True,
                        "points": [
                            {
                                "time": "20:00",
                                "tz_city": "London",
                                "event_title": "созвон",
                            }
                        ],
                    }
                )
            )
        )
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("src.event_detection.detector.AsyncOpenAI", return_value=mock_client):
        result = await detect_event(
            current_msg={
                "author_id": "888",
                "author_name": "Boss",
                "text": "Call at 8pm London",
                "timestamp_utc": "2026-03-14T20:00:00Z",
            },
            chat_id="chat1",
        )

    assert result["time_mentioned"] is False
    assert result["points"] == []


@pytest.mark.asyncio
async def test_llm_wrong_top_level_types_fail_silent():
    from src.event_detection.detector import detect_event

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({"time_mentioned": "yes", "points": {}})
            )
        )
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("src.event_detection.detector.AsyncOpenAI", return_value=mock_client):
        result = await detect_event(
            current_msg={
                "author_id": "888",
                "author_name": "Boss",
                "text": "Call at 8pm London",
                "timestamp_utc": "2026-03-14T20:00:00Z",
            },
            chat_id="chat1",
        )

    assert result["time_mentioned"] is False
    assert result["points"] == []


def test_runtime_prompt_mentions_v5_fields():
    from src.event_detection.prompts import get_system_prompt

    prompt = get_system_prompt()
    assert "time_mentioned" in prompt
    assert "tz_city" in prompt
    assert "am_pm_clear" in prompt


def test_fallback_attempt_does_not_reuse_primary_key_for_different_provider(
    monkeypatch,
):
    from src.event_detection.detector import _build_llm_attempts, clear_runtime_caches

    monkeypatch.setenv("LLM_API_KEY", "primary-key")
    monkeypatch.delenv("LLM_FALLBACK_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    clear_runtime_caches()

    with patch(
        "src.event_detection.detector.get_config",
        return_value={
            "llm": {
                "model": "primary-model",
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                "api_key_env": "LLM_API_KEY",
                "fallback": {
                    "enabled": True,
                    "model": "fallback-model",
                    "base_url": "https://api.groq.com/openai/v1",
                    "api_key_env": "LLM_FALLBACK_API_KEY",
                },
            }
        },
    ):
        attempts = _build_llm_attempts()

    assert len(attempts) == 1
    assert attempts[0]["name"] == "primary"
