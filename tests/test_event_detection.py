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
async def test_process_message_trigger():
    """Test that process_message calls the detector and returns the result."""
    mock_result = {
        "trigger": True,
        "polarity": "positive",
        "confidence": 0.9,
        "reason": "Test reason",
        "times": ["15:00"],
        "event_location": None
    }
    
    with patch("src.event_detection.detect_event", new_callable=AsyncMock) as mock_detect:
        mock_detect.return_value = mock_result
        
        res = await process_message(
            message_text="Let's meet at 15:00",
            chat_id="123",
            user_id="456",
            platform="telegram",
            author_name="John",
            timestamp_utc="2026-03-05T10:00:00Z"
        )
        
        assert res["trigger"] is True
        assert res["times"] == ["15:00"]
        mock_detect.assert_called_once()

@pytest.mark.asyncio
async def test_chat_lock_concurrency():
    """Test that a second message in the same chat returns early if lock is held."""
    # We'll mock detect_event to hang for a bit
    async def slow_detect(*args):
        await asyncio.sleep(0.5)
        return {"trigger": False, "confidence": 0.0, "times": [], "event_location": None}

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
        
        # res2 should return immediately with trigger=False because lock is held
        assert res2["trigger"] is False
        assert "lock" in res2["reason"].lower()
        
        await task1
