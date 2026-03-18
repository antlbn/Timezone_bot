import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message

from src.utils import auto_cleanup, delete_message_after

@pytest.fixture
def mock_message():
    message = MagicMock(spec=Message)
    message.delete = AsyncMock()
    message.chat = MagicMock()
    message.chat.type = "group"
    return message


@pytest.mark.asyncio
async def test_delete_message_after(mock_message):
    """Test that the helper actually sleeps and deletes."""
    # Run with a 0 delay to see it skip
    await delete_message_after(mock_message, 0)
    mock_message.delete.assert_not_called()
    
    # Run with a small delay
    # We can't easily assert on the sleep itself without mocking asyncio.sleep,
    # but we can verify it calls delete().
    await delete_message_after(mock_message, 0.01)
    mock_message.delete.assert_called_once()


@pytest.mark.asyncio
async def test_auto_cleanup_decorator_schedules_tasks(mock_message, monkeypatch):
    """Test that the decorator spawns tasks for deletion."""
    
    # Mock config to return a 1 second timeout
    mock_get_timeout = MagicMock(return_value=1)
    monkeypatch.setattr("src.utils.get_settings_cleanup_timeout", mock_get_timeout)
    
    # Mock create_task so we don't actually wait
    def mock_create_task_side_effect(coro):
        coro.close()
        return MagicMock()
        
    mock_create_task = MagicMock(side_effect=mock_create_task_side_effect)
    monkeypatch.setattr("src.utils.asyncio.create_task", mock_create_task)
    
    # Create a dummy handler
    bot_reply_mock = MagicMock(spec=Message)
    bot_reply_mock.delete = AsyncMock()
    
    @auto_cleanup(delete_bot_msg=True)
    async def dummy_handler(msg: Message):
        return bot_reply_mock
        
    result = await dummy_handler(mock_message)
    
    assert result is bot_reply_mock
    # Should schedule 2 tasks: one for the user command, one for the bot reply
    assert mock_create_task.call_count == 2


@pytest.mark.asyncio
async def test_auto_cleanup_no_bot_msg(mock_message, monkeypatch):
    """Test when the handler doesn't return a bot message or delete_bot_msg is False."""
    
    mock_get_timeout = MagicMock(return_value=1)
    monkeypatch.setattr("src.utils.get_settings_cleanup_timeout", mock_get_timeout)
    
    def mock_create_task_side_effect(coro):
        coro.close()
        return MagicMock()
        
    mock_create_task = MagicMock(side_effect=mock_create_task_side_effect)
    monkeypatch.setattr("src.utils.asyncio.create_task", mock_create_task)
    
    @auto_cleanup(delete_bot_msg=False)
    async def dummy_handler(msg: Message):
        return MagicMock(spec=Message) # returning it, but shouldn't delete because flag is False
        
    await dummy_handler(mock_message)
    
    # Should schedule exactly 1 task: for the user command only
    assert mock_create_task.call_count == 1
