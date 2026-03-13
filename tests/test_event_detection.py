import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.event_detection import process_message
from src.event_detection.history import _message_history, _chat_locks


@pytest.fixture(autouse=True)
def clear_history():
    _message_history.clear()
    _chat_locks.clear()


@pytest.mark.asyncio
async def test_process_message_event():
    """Test that process_message calls the detector and returns the new schema result."""
    mock_result = {
        "event": True,
        "sender_id": "456",
        "sender_name": "John",
        "time": ["15:00"],
        "city": [None],
        "reflections": {}
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
            sender_db={"timezone": "Europe/London", "city": "London"}
        )

        assert res["event"] is True
        assert res["time"] == ["15:00"]
        assert res["sender_id"] == "456"
        mock_detect.assert_called_once()


@pytest.mark.asyncio
async def test_chat_lock_concurrency():
    """Test that a second message in the same chat returns early if lock is held."""
    # We'll mock detect_event to hang for a bit
    async def slow_detect(*args, **kwargs):
        await asyncio.sleep(0.5)
        return {"event": False, "time": [], "city": [], "sender_id": "", "sender_name": ""}

    with patch("src.event_detection.detect_event", side_effect=slow_detect):
        # Fire first message (it will hold the lock for 0.5s)
        task1 = asyncio.create_task(process_message(
            "Msg 1", "chat1", "user1", "telegram", "John", "2026-03-05T10:00:00Z"
        ))

        # Wait a bit to ensure task1 started and took the lock
        await asyncio.sleep(0.1)

        # Fire second message in same chat
        res2 = await process_message(
            "Msg 2", "chat1", "user2", "telegram", "Doe", "2026-03-05T10:00:10Z"
        )

        # res2 should return immediately with event=False because lock is held
        assert res2["event"] is False
        assert "lock" in res2.get("reason", "").lower()

        await task1

@pytest.mark.asyncio
async def test_llm_tool_call_dispatch(monkeypatch):
    """Test that detector correctly handles an actual tool_call from the LLM."""
    from src.event_detection.detector import detect_event
    from unittest.mock import MagicMock
    import json

    # 1. Сборка фейкового ответа OpenAI (как будто модель вызвала tool)
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "convert_time"
    mock_tool_call.function.arguments = json.dumps({
        "sender_id": "888",
        "sender_name": "Boss",
        "time": ["20:00"],
        "city": ["London"]
    })

    mock_choice = MagicMock()
    mock_choice.finish_reason = "tool_calls"
    mock_choice.message.tool_calls = [mock_tool_call]

    # Мокаем вызов LLM
    mock_call_llm = AsyncMock(return_value=mock_choice)
    monkeypatch.setattr("src.event_detection.detector.call_llm", mock_call_llm)

    # 2. Мокаем сам tool (execute_convert_time), чтобы убедиться, что он был вызван
    mock_execute = AsyncMock()
    monkeypatch.setattr("src.event_detection.tools.execute_convert_time", mock_execute)

    # 3. Вызываем detect_event
    result = await detect_event(
        current_msg={"author_id": "888", "author_name": "Boss", "text": "Call at 8pm London"},
        snapshot=[],
        sender_db={},
        send_fn=AsyncMock(), # Передаем фейковую отправку
        platform="telegram",
        chat_id="chat1"
    )

    # 4. Проверяем, что execute_convert_time был вызван с правильными аргументами из tool_call
    mock_execute.assert_called_once()
    kwargs = mock_execute.call_args.kwargs
    assert kwargs["sender_id"] == "888"
    assert kwargs["times"] == ["20:00"]
    assert kwargs["cities"] == ["London"]
    
    # 5. Проверяем, что детектор вернул заглушку для логов
    assert result["event"] is True
    assert result["time"] == ["20:00"]
