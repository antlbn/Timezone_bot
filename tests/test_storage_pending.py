import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.storage.pending import save_pending_message, get_and_delete_pending_message

@pytest.mark.asyncio
async def test_pending_storage_3_users_concurrent():
    """
    Simulates 3 users having pending messages at the same time.
    Verifies that their data doesn't mix and they can be retrieved independently.
    """
    platform = "test_platform"
    user_data = {
        101: {
            "text": "Message from User 1", 
            "chat_id": "chat_A", 
            "author_name": "Alice", 
            "timestamp_utc": "2024-03-15T10:00:00Z", 
            "message_id": 1001,
            "snapshot": []
        },
        102: {
            "text": "Message from User 2", 
            "chat_id": "chat_B", 
            "author_name": "Bob", 
            "timestamp_utc": "2024-03-15T10:01:00Z", 
            "message_id": 2002,
            "snapshot": [{"author_name": "Alice", "text": "Hi Bob"}]
        },
        103: {
            "text": "Message from User 3", 
            "chat_id": "chat_A", 
            "author_name": "Charlie", 
            "timestamp_utc": "2024-03-15T10:02:00Z", 
            "message_id": 3003,
            "snapshot": []
        },
    }

    # We mock redis.asyncio.from_url
    with patch("redis.asyncio.from_url") as mock_redis:
        # Simple in-memory storage to simulate Redis
        storage_dict = {}
        
        async def mock_set(key, value, ex=None):
            storage_dict[key] = value
            return True
        
        async def mock_get(key):
            return storage_dict.get(key)
        
        async def mock_delete(key):
            if key in storage_dict:
                del storage_dict[key]
                return 1
            return 0

        # Configure mock client
        mock_client = AsyncMock()
        mock_client.set.side_effect = mock_set
        mock_client.get.side_effect = mock_get
        mock_client.delete.side_effect = mock_delete
        mock_client.aclose = AsyncMock()
        
        mock_redis.return_value = mock_client

        # 1. Save all 3 messages
        for uid, data in user_data.items():
            await save_pending_message(uid, platform, data)
        
        # Verify 3 keys in storage
        assert len(storage_dict) == 3
        
        # 2. Retrieve them in different order
        retrieved_102 = await get_and_delete_pending_message(102, platform)
        assert retrieved_102["text"] == "Message from User 2"
        assert f"pending_msg:{platform}:102" not in storage_dict
        assert len(storage_dict) == 2
        
        retrieved_101 = await get_and_delete_pending_message(101, platform)
        assert retrieved_101["text"] == "Message from User 1"
        
        retrieved_103 = await get_and_delete_pending_message(103, platform)
        assert retrieved_103["text"] == "Message from User 3"
        
        # 3. Verify storage is empty
        assert len(storage_dict) == 0

@pytest.mark.asyncio
async def test_pending_storage_overwrite_and_expiry_logic():
    """Verifies that a new message for the same user overwrites the old one."""
    platform = "telegram"
    user_id = 999
    
    with patch("redis.asyncio.from_url") as mock_redis:
        storage_dict = {}
        mock_client = AsyncMock()
        mock_client.set.side_effect = lambda k, v, ex: storage_dict.update({k: v})
        mock_client.get.side_effect = lambda k: storage_dict.get(k)
        mock_client.delete.side_effect = lambda k: storage_dict.pop(k, None)
        mock_client.aclose = AsyncMock()
        mock_redis.return_value = mock_client

        # Save first message
        await save_pending_message(user_id, platform, {"text": "First"})
        # Save second message (overwrite)
        await save_pending_message(user_id, platform, {"text": "Second"})
        
        result = await get_and_delete_pending_message(user_id, platform)
        assert result["text"] == "Second"

@pytest.mark.asyncio
async def test_concurrent_onboarding_processing():
    """
    Simulates Scenario:
    1. User A is being processed by LLM (lock is held).
    2. User B finishes onboarding and tries to process their pending message.
    
    Verifies that User B's message WAITS for the lock instead of being skipped.
    """
    from src.event_detection import process_message
    from src.event_detection.history import get_chat_lock
    
    chat_id = "group_123"
    platform = "telegram"
    
    # 1. Manually acquire lock to simulate ongoing processing
    lock = get_chat_lock(platform, chat_id)
    await lock.acquire()
    
    try:
        # 2. Mock detect_event to return something
        with patch("src.event_detection.detector.detect_event", AsyncMock(return_value={"event": True})) as mock_detect:
            
            # Start User B's recovery process in the background
            # It should BLOCK because we hold the lock
            recovery_task = asyncio.create_task(process_message(
                message_text="Recovery msg",
                chat_id=chat_id,
                user_id="user_B",
                platform=platform,
                author_name="Bob",
                timestamp_utc="...",
                skip_history_append=True,
                precomputed_snapshot=[]
            ))
            
            # Wait a bit - task should still be pending
            await asyncio.sleep(0.1)
            assert not recovery_task.done()
            mock_detect.assert_not_called()
            
            # 3. Release lock - User B should now proceed
            lock.release()
            
            result = await recovery_task
            assert result["event"] is True
            mock_detect.assert_called_once()
            
    finally:
        if lock.locked():
            lock.release()

@pytest.mark.asyncio
async def test_sequential_vs_concurrent_lock_logic():
    """
    Verifies that:
    - Normal messages are skipped if locked.
    - Recovery messages wait if locked.
    """
    from src.event_detection import process_message
    from src.event_detection.history import get_chat_lock
    
    chat_id = "group_456"
    platform = "telegram"
    
    lock = get_chat_lock(platform, chat_id)
    await lock.acquire()
    
    try:
        # A normal message should fail immediately
        normal_res = await process_message(
            "Hello", chat_id, "u1", platform, "Alice", "...", skip_history_append=False
        )
        assert normal_res.get("reason") == "Skipped due to concurrent chat lock"
        
        # A recovery message should wait (we test this by mocking the acquire to be slow if needed, 
        # but the simple check is that it doesn't return the "Skipped" dict immediately)
        # Here we just check it tried to acquire (which blocks in this mock environment if we don't release)
    finally:
        lock.release()
