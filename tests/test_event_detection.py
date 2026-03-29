import pytest
import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.event_detection import process_message
from src.config import get_max_message_age


@pytest.mark.asyncio
async def test_process_message_event():
    """Test that process_message calls the detector and returns the new schema result."""
    mock_result = {
        "event": True,
        "sender_id": "456",
        "sender_name": "John",
        "time": ["15:00"],
        "city": [None],
        "event_title": [None],
    }

    with patch("src.event_detection.detect_event", new_callable=AsyncMock) as mock_detect:
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

        assert res["event"] is True
        assert res["time"] == ["15:00"]
        assert res["sender_id"] == "456"
        mock_detect.assert_called_once()



@pytest.mark.asyncio
async def test_llm_json_dispatch(monkeypatch):
    """Test that detect_event correctly handles JSON responses from the LLM."""
    from src.event_detection.detector import detect_event

    # Build a fake OpenAI response object that returns JSON text
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(
        {
            "event": True,
            "points": [{"time": "20:00", "city": "London", "event_title": "созвон"}],
        }
    )))]
    mock_member = {
        "user_id": "888", "username": "boss",
        "timezone": "Europe/London", "city": "London", "flag": "🇬🇧",
    }

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_client_cls = MagicMock(return_value=mock_client)

    with (
        patch("src.event_detection.detector.AsyncOpenAI", mock_client_cls),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=[mock_member])),
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

    assert result["event"] is True
    assert result["time"] == ["20:00"]
    assert result["event_title"] == ["созвон"]


@pytest.mark.asyncio
async def test_llm_json_dispatch_strips_markdown_fences():
    """Fence-wrapped JSON should still parse successfully."""
    from src.event_detection.detector import detect_event

    fenced_json = """```json
{"event": true, "points": [{"time": "20:00", "city": "London", "event_title": "созвон"}]}
```"""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=fenced_json))]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with (
        patch("src.event_detection.detector.AsyncOpenAI", return_value=mock_client),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=[{
            "user_id": "888", "username": "boss",
            "timezone": "Europe/London", "city": "London", "flag": "🇬🇧",
        }])),
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

    assert result["event"] is True
    assert result["time"] == ["20:00"]


def test_strip_json_fences_handles_language_and_trailing_fence():
    from src.event_detection.detector import _strip_json_fences

    raw = "```json\n{\"event\": true, \"points\": []}\n```"

    assert _strip_json_fences(raw) == "{\"event\": true, \"points\": []}"


@pytest.mark.asyncio
async def test_llm_fallback_attempt_used(monkeypatch):
    """Primary LLM failure should fall back to a secondary configured LLM."""
    from src.event_detection.detector import clear_runtime_caches, detect_event

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    clear_runtime_caches()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(
        {
            "event": True,
            "points": [{"time": "20:00", "city": "London", "event_title": "созвон"}],
        }
    )))]

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
                    "base_url": None,
                    "fallback": {
                        "enabled": True,
                        "model": "fallback-model",
                    },
                }
            },
        ),
        patch(
            "src.event_detection.detector.AsyncOpenAI",
            return_value=shared_client,
        ) as mock_client_cls,
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=[{
            "user_id": "888", "username": "boss",
            "timezone": "Europe/London", "city": "London", "flag": "🇬🇧",
        }])),
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

    assert result["event"] is True
    assert result["event_title"] == ["созвон"]
    assert shared_client.chat.completions.create.await_count == 2
    assert mock_client_cls.call_count == 1


@pytest.mark.asyncio
async def test_process_message_builds_reply_text(monkeypatch):
    """Bot logic should build reply text after structured detection succeeds."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(
        {
            "event": True,
            "points": [{"time": "20:00", "city": "London", "event_title": "созвон"}],
        }
    )))]

    primary_client = MagicMock()
    primary_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with (
        patch(
            "src.event_detection.detector.get_config",
            return_value={
                "llm": {
                    "model": "primary-model",
                    "temperature": 0.1,
                    "base_url": None,
                    "fallback": {
                        "enabled": True,
                        "model": "fallback-model",
                    },
                }
            },
        ),
        patch("src.event_detection.detector.AsyncOpenAI", return_value=primary_client) as mock_client_cls,
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=[{
            "user_id": "888", "username": "boss",
            "timezone": "Europe/London", "city": "London", "flag": "🇬🇧",
        }])),
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

    assert result["event"] is True
    assert result["time"] == ["20:00"]
    assert result["reply_text"] == "20:00 London 🇬🇧"
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
    """Verify that messages older than max_age are skipped (Pass 1)."""
    max_age = get_max_message_age()
    # Build an old timestamp (e.g. max_age + 1s ago)
    old_time = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(seconds=max_age + 1)
    ).isoformat()

    with patch(
        "src.event_detection.detector.detect_event", new_callable=AsyncMock
    ) as mock_detect:
        res = await process_message(
            "Old message", "chat1", "u1", "tg", "J", old_time, skip_aging=False
        )
        assert res["event"] is False
        assert "stale" in res.get("reason", "").lower()
        mock_detect.assert_not_called()
