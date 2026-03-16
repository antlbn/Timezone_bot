import pytest
import asyncio
import datetime
from unittest.mock import AsyncMock, patch
from src.storage.pending import save_pending_message, get_and_delete_pending_messages
from src.event_detection import process_message
from src.event_detection.history import get_chat_lock

@pytest.mark.asyncio
async def test_pending_storage_memory_logic():
    """Verifies in-memory pending storage."""
    platform = "test"
    uid = 101
    await save_pending_message(uid, platform, {"text": "hello"})
    res = await get_and_delete_pending_messages(uid, platform)
    assert len(res) == 1
    assert res[0]["text"] == "hello"
    assert await get_and_delete_pending_messages(uid, platform) == []

@pytest.mark.asyncio
async def test_waiting_lock_queuing():
    """Verifies that messages wait for lock and mocks work."""
    chat_id = "group_1"
    platform = "telegram"
    lock = get_chat_lock(platform, chat_id)
    
    await lock.acquire()
    try:
        # Patch detect_event IN THE NAMESPACE WHERE IT IS USED (src.event_detection)
        with patch("src.event_detection.detect_event", AsyncMock(return_value={"event": True})) as mock_detect:
            msg_task = asyncio.create_task(process_message(
                "Hello", chat_id, "u1", platform, "Alice", 
                datetime.datetime.now(datetime.timezone.utc).isoformat()
            ))
            
            await asyncio.sleep(0.1)
            assert not msg_task.done()
            lock.release()
            
            result = await msg_task
            assert result.get("event") is True
            mock_detect.assert_called_once()
    finally:
        if lock.locked(): lock.release()

@pytest.mark.asyncio
async def test_message_aging_while_waiting():
    """Verifies aging skip after queue."""
    chat_id = "group_3"
    platform = "telegram"
    lock = get_chat_lock(platform, chat_id)
    
    fresh_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await lock.acquire()
    
    try:
        # Patch get_max_message_age IN THE NAMESPACE WHERE IT IS USED
        with patch("src.event_detection.get_max_message_age", return_value=1):
            with patch("src.event_detection.detect_event", AsyncMock()) as mock_detect:
                msg_task = asyncio.create_task(process_message(
                    "Waiting msg", chat_id, "u1", platform, "Alice", fresh_time
                ))
                
                await asyncio.sleep(1.5)
                lock.release()
                
                result = await msg_task
                assert "Message stale after queueing" in result.get("reason")
                mock_detect.assert_not_called()
    finally:
        if lock.locked(): lock.release()
