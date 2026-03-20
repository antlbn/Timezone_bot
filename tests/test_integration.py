import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.event_detection import process_message


@pytest.mark.asyncio
async def test_full_pipeline_integration():
    """
    Simulates: Message → process_message → detect_event (LangChain agent)
               → publish_event tool call → _build_reply → send_fn

    Ensures that multiple time points from the LLM result in a single
    aggregated message via the publish_event tool.
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

    # 2. LangChain mock: agent returns a tool_call for publish_event
    points_payload = [
        {"time": "10:30", "city": None, "event_type": "event 1"},
        {"time": "15:00", "city": None, "event_type": "event 2"},
    ]

    mock_response = MagicMock()
    mock_response.tool_calls = [
        {
            "name": "publish_event",
            "args": {"points": points_payload},
            "id": "call_abc",
        }
    ]
    mock_response.content = ""

    # Patch ChatOpenAI class-level in detector to bypass API key check
    mock_llm_with_tools = MagicMock()
    mock_llm_with_tools.ainvoke = AsyncMock(return_value=mock_response)
    mock_llm_instance = MagicMock()
    mock_llm_instance.bind_tools = MagicMock(return_value=mock_llm_with_tools)
    mock_llm_cls = MagicMock(return_value=mock_llm_instance)

    # 3. Capture sent messages
    sent_messages = []

    async def mock_send(text):
        sent_messages.append(text)
        return "msg_999"

    # 4. Execute Pipeline
    with (
        patch("src.event_detection.detector.ChatOpenAI", mock_llm_cls),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=mock_members)),
    ):
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

    # 5. Assertions — exactly ONE aggregated message
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
