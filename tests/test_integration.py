import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from src.event_detection import process_message


@pytest.mark.asyncio
async def test_full_pipeline_integration(monkeypatch):
    """
    Simulates: Message -> process_message -> detect_event -> tool_call -> execute_convert_time -> formatter -> send_fn
    Ensures that multiple time points from the LLM result in a single aggregated message.
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

    # 2. Mock LLM Response (JSON with 2 points)
    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message.content = json.dumps(
        {
            "reflections": {
                "event_logic": "test",
                "time_logic": "test",
                "geo_logic": "test",
            },
            "event": True,
            "sender_id": user_id,
            "sender_name": sender_name,
            "points": [
                {"time": "10:30", "city": None, "event_type": "event 1"},
                {"time": "15:00", "city": None, "event_type": "event 2"},
            ],
        }
    )
    mock_choice.message.tool_calls = None

    # 3. Apply Mocks
    # Mock LLM call
    mock_call_llm = AsyncMock(return_value=mock_choice)
    monkeypatch.setattr("src.event_detection.detector.call_llm", mock_call_llm)

    # Mock Storage
    monkeypatch.setattr(
        "src.storage.storage.get_chat_members", AsyncMock(return_value=mock_members)
    )

    # Mock send_fn to capture output
    sent_messages = []

    async def mock_send(text):
        sent_messages.append(text)

    # 4. Execute Pipeline
    await process_message(
        message_text=text,
        chat_id=chat_id,
        user_id=user_id,
        platform="discord",
        author_name=sender_name,
        timestamp_utc="2026-03-14T20:00:00Z",
        sender_db=sender_db,
        send_fn=mock_send,
        skip_aging=True,
    )

    # 5. Assertions
    # We expect exactly ONE message because of our new aggregation logic
    assert len(sent_messages) == 1, f"Expected 1 message, got {len(sent_messages)}"

    reply = sent_messages[0]
    print(f"\nCaptured Integrated Reply:\n{reply}")

    # Check that both times are present in the single message
    assert "10:30 Sarajevo 🇧🇦" in reply
    assert "15:00 Sarajevo 🇧🇦" in reply
    # Check formatting
    lines = [line for line in reply.split("\n") if line.strip()]
    assert lines[0] == "Anton:"
    assert lines[1] == "event 1"
    assert "10:30 Sarajevo 🇧🇦" in lines[2]
    assert "09:30 London 🇬🇧" in lines[3]
    assert lines[4] == "event 2"
    assert "15:00 Sarajevo 🇧🇦" in lines[5]
    assert "14:00 London 🇬🇧" in lines[6]
