import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.event_detection import process_message


@pytest.mark.asyncio
async def test_full_pipeline_integration():
    """
    Simulates: Message → process_message → detect_event JSON output
               → _build_reply → send_fn

    Ensures that multiple time points from the LLM result in a single
    aggregated message from a single JSON response.
    """

    # 1. Mock Data
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

    # 2. OpenAI mock: model returns canonical JSON content
    points_payload = [
        {"time": "10:30", "city": None, "event_title": "event 1"},
        {"time": "15:00", "city": None, "event_title": "event 2"},
    ]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(
        {
            "event": True,
            "points": points_payload,
        }
    )))]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_client_cls = MagicMock(return_value=mock_client)

    # 4. Execute Pipeline
    with (
        patch("src.event_detection.detector.AsyncOpenAI", mock_client_cls),
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
    print(f"\nCaptured Integrated Reply:\n{reply}")

    # Check that both times are present in the single message
    assert "10:30 Sarajevo 🇧🇦" in reply
    assert "15:00 Sarajevo 🇧🇦" in reply
    # Check formatting
    lines = [line for line in reply.split("\n") if line.strip()]
    assert lines[0] == "10:30 Sarajevo 🇧🇦"
    assert "09:30 London 🇬🇧" in lines[1]
    assert "15:00 Sarajevo 🇧🇦" in lines[2]
    assert "14:00 London 🇬🇧" in lines[3]
