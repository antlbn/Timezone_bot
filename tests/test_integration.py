import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.event_detection import process_message


@pytest.mark.asyncio
async def test_full_pipeline_integration():
    chat_id = "integration_chat_123"
    user_id = "user_anton"
    sender_name = "Anton"
    text = "Let's sync at 10:30 and then again at 15:00"

    sender_db = {"timezone": "Europe/Sarajevo", "city": "Sarajevo", "flag": "🇧🇦"}

    mock_members = [
        {
            "user_id": user_id,
            "username": "anton",
            "timezone": "Europe/Sarajevo",
            "city": "Sarajevo",
            "flag": "🇧🇦",
        },
        {
            "user_id": "user_jane",
            "username": "jane",
            "timezone": "Europe/London",
            "city": "London",
            "flag": "🇬🇧",
        },
    ]

    points_payload = [
        {"time": "10:30", "tz_city": None, "event_title": "event 1", "am_pm_clear": True},
        {"time": "15:00", "tz_city": None, "event_title": "event 2", "am_pm_clear": True},
    ]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(
        {"time_mentioned": True, "points": points_payload}
    )))]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with (
        patch("src.event_detection.detector.AsyncOpenAI", return_value=mock_client),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=mock_members)),
    ):
        result = await process_message(
            message_text=text,
            chat_id=chat_id,
            user_id=user_id,
            platform="discord",
            author_name=sender_name,
            timestamp_utc="2026-03-14T20:00:00Z",
            sender_db=sender_db,
            skip_aging=True,
        )

    reply = result["reply_text"]
    assert "10:30 Sarajevo" in reply
    assert "15:00 Sarajevo" in reply
    assert "09:30 London" in reply
    assert "14:00 London" in reply


@pytest.mark.asyncio
async def test_ambiguous_points_render_with_prefix():
    chat_id = "integration_chat_123"
    user_id = "user_anton"
    sender_db = {"timezone": "Europe/Sarajevo", "city": "Sarajevo", "flag": "🇧🇦"}
    mock_members = [
        {
            "user_id": user_id,
            "username": "anton",
            "timezone": "Europe/Sarajevo",
            "city": "Sarajevo",
            "flag": "🇧🇦",
        }
    ]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(
        {
            "time_mentioned": True,
            "points": [
                {"time": "08:00", "tz_city": None, "event_title": None, "am_pm_clear": False},
                {"time": "15:00", "tz_city": None, "event_title": None, "am_pm_clear": True},
            ],
        }
    )))]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with (
        patch("src.event_detection.detector.AsyncOpenAI", return_value=mock_client),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=mock_members)),
    ):
        result = await process_message(
            message_text="tomorrow at 8 and 15:00",
            chat_id=chat_id,
            user_id=user_id,
            platform="discord",
            author_name="Anton",
            timestamp_utc="2026-03-14T20:00:00Z",
            sender_db=sender_db,
            skip_aging=True,
        )

    assert "08:00 Sarajevo" in result["reply_text"]
    assert "15:00 Sarajevo" in result["reply_text"]


@pytest.mark.asyncio
async def test_invalid_points_only_produce_no_reply():
    chat_id = "integration_chat_123"
    user_id = "user_anton"
    sender_db = {"timezone": "Europe/Sarajevo", "city": "Sarajevo", "flag": "🇧🇦"}

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(
        {
            "time_mentioned": True,
            "points": [{"time": "99:99", "tz_city": None, "event_title": None, "am_pm_clear": True}],
        }
    )))]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("src.event_detection.detector.AsyncOpenAI", return_value=mock_client):
        result = await process_message(
            message_text="broken point",
            chat_id=chat_id,
            user_id=user_id,
            platform="discord",
            author_name="Anton",
            timestamp_utc="2026-03-14T20:00:00Z",
            sender_db=sender_db,
            skip_aging=True,
        )

    assert result["time_mentioned"] is False
    assert result["reply_text"] is None
