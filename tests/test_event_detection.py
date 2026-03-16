import pytest
import asyncio
import datetime
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
            sender_db={"timezone": "Europe/London", "city": "London"},
            skip_aging=True
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
            "Msg 1", "chat1", "user1", "telegram", "John", "2026-03-05T10:00:00Z", skip_aging=True
        ))

        # Wait a bit to ensure task1 started and took the lock
        await asyncio.sleep(0.1)

        # Fire second message in same chat
        # Now it will WAIT instead of returning immediately
        task2 = asyncio.create_task(process_message(
            "Msg 2", "chat1", "user2", "telegram", "Doe", "2026-03-05T10:00:10Z", skip_aging=True
        ))

        # verify that task2 is not done yet
        await asyncio.sleep(0.1)
        assert not task2.done(), "Task 2 should be waiting for the lock"

        await task1
        res2 = await task2
        
        # res2 should eventually succeed (event=False as per slow_detect, but it waited)
        assert res2["event"] is False

@pytest.mark.asyncio
async def test_llm_json_dispatch(monkeypatch):
    """Test that detector correctly handles an actual JSON response from the LLM."""
    from src.event_detection.detector import detect_event
    from unittest.mock import MagicMock
    import json

    # 1. Сборка фейкового ответа OpenAI (JSON в контенте)
    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message.content = json.dumps({
        "reflections": {"event_logic": "test", "time_logic": "test", "geo_logic": "test"},
        "event": True,
        "sender_id": "888",
        "sender_name": "Boss",
        "points": [{"time": "20:00", "city": "London"}]
    })
    mock_choice.message.tool_calls = None

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
        send_fn=AsyncMock(),
        platform="telegram",
        chat_id="chat1"
    )

    # 4. Проверяем, что execute_convert_time был вызван
    mock_execute.assert_called_once()
    kwargs = mock_execute.call_args.kwargs
    assert kwargs["sender_id"] == "888"
    assert kwargs["points"] == [{"time": "20:00", "city": "London"}]
    
    assert result["event"] is True
    assert result["time"] == ["20:00"]
    assert result["points"] == [{"time": "20:00", "city": "London"}]

@pytest.mark.asyncio
async def test_message_aging_pre_lock():
    """Verify that a message already older than max_age is skipped before locking."""
    # Build an old timestamp (e.g. 60s ago)
    old_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=60)).isoformat()
    
    with patch("src.event_detection.detect_event", new_callable=AsyncMock) as mock_detect:
        res = await process_message(
            "Old message", "chat1", "u1", "tg", "J", old_time, skip_aging=False
        )
        assert res["event"] is False
        assert "stale" in res.get("reason", "").lower()
        mock_detect.assert_not_called()

@pytest.mark.asyncio
async def test_message_aging_post_lock():
    """Verify that a message is skipped if it becomes old while waiting for the lock."""
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    # Message is fresh now
    msg_time = now.isoformat()
    
    # Mock a long-running detection that will hold the lock
    async def fast_detect(*args, **kwargs):
        return {"event": False}

    with patch("src.event_detection.detect_event", side_effect=fast_detect):
        lock = _chat_locks[("tg", "chat1")] = asyncio.Lock()
        await lock.acquire() # Hold the lock manually
        
        # Start processing Msg 2 (it's fresh)
        task = asyncio.create_task(process_message(
            "Msg 2", "chat1", "u2", "tg", "J", msg_time, skip_aging=False
        ))
        
        await asyncio.sleep(0.1) # Let it hit the lock
        
        # Now artificially age the message by waiting longer than max_age (30s)
        # We don't want to actually sleep 30s in tests, so we'll mock datetime.now
        future_now = now + datetime.timedelta(seconds=40)
        
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value = future_now
            mock_dt.fromisoformat.side_effect = datetime.datetime.fromisoformat
            mock_dt.timezone = datetime.timezone
            
            lock.release() # Release lock, allowing Task to continue
            res = await task
            
            assert res["event"] is False
            assert "stale" in res.get("reason", "").lower()
