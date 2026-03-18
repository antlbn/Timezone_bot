import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, Chat, User
from aiogram.fsm.context import FSMContext

# Import handlers to test
from src.commands.settings import process_city
from src.commands.common import handle_time_mention, cmd_me, cmd_settz
from src.commands.states import SetTimezone

@pytest.fixture
def mock_storage_and_cache(monkeypatch):
    """Mock the storage singleton and cache."""
    storage_mock = AsyncMock()
    cache_mock = AsyncMock()
    # Apply mocks to the modules where they are used
    monkeypatch.setattr("src.commands.settings.storage", storage_mock)
    monkeypatch.setattr("src.commands.common.storage", storage_mock)  # <-- ADDED
    monkeypatch.setattr("src.commands.common.get_user_cached", cache_mock)
    monkeypatch.setattr("src.commands.settings.invalidate_user_cache", MagicMock())
    return storage_mock, cache_mock

@pytest.fixture
def mock_message():
    """Create a mock Aiogram Message."""
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 12345
    message.from_user.username = "testuser"
    message.from_user.first_name = "Test"
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 12345
    message.chat.type = "group"
    message.answer = AsyncMock()
    message.reply = AsyncMock()
    message.message_id = 1
    message.reply_to_message = None  # Default to no reply
    return message

@pytest.fixture
def mock_state():
    """Create a mock FSMContext."""
    state = AsyncMock(spec=FSMContext)
    # Mock get_data to return empty dict by default
    state.get_data.return_value = {}
    return state

@pytest.mark.asyncio
async def test_cmd_me_exists(mock_storage_and_cache, mock_message):
    """Test /tb_me when user exists in DB."""
    mock_storage, mock_cache = mock_storage_and_cache
    # Setup mock return value
    mock_cache.return_value = {
        "city": "Berlin",
        "timezone": "Europe/Berlin",
        "flag": "🇩🇪"
    }

    # Run handler
    await cmd_me(mock_message)

    # Verify cache called (CMD ME uses cache now)
    mock_cache.assert_called_once_with(12345, platform="telegram")
    
    # Verify reply
    mock_message.reply.assert_called_once()
    args, _ = mock_message.reply.call_args
    assert "Your timezone is set to" in args[0]

@pytest.mark.asyncio
async def test_cmd_me_not_exists(mock_storage_and_cache, mock_message):
    """Test /tb_me when user does NOT exist."""
    _, mock_cache = mock_storage_and_cache
    mock_cache.return_value = None

    await cmd_me(mock_message)

    # Verify reply
    mock_message.reply.assert_called_once()
    args, _ = mock_message.reply.call_args
    assert "You haven't set your timezone yet" in args[0]

@pytest.mark.asyncio
async def test_cmd_settz_start(mock_message, mock_state):
    """Test /tb_settz entry point."""
    mock_message.chat.type = "private"
    with patch("src.commands.settings.dm_onboarding_start", AsyncMock()) as mock_start:
        await cmd_settz(mock_message, mock_state)
        mock_start.assert_called_once()

    # Verify prompt to user (it's actually handled inside dm_onboarding_start now, 
    # but the test was already patching it)
    pass


@pytest.mark.asyncio
async def test_process_city_success(mock_storage_and_cache, mock_message, mock_state, monkeypatch):
    """Test successful city selection."""
    mock_storage, _ = mock_storage_and_cache
    # Mock geo logic
    # We need to mock 'src.commands.settings.geo'
    mock_geo = MagicMock()
    mock_geo.get_timezone_by_city.return_value = {
        "city": "Paris",
        "timezone": "Europe/Paris",
        "flag": "🇫🇷"
    }
    monkeypatch.setattr("src.commands.settings.geo", mock_geo)

    # Setup message text
    mock_message.text = "Paris"
    
    # Setup state data (user_id check)
    mock_state.get_data.return_value = {"user_id": 12345}

    # Setup reply_to_message (must be present and from bot)
    mock_reply = MagicMock(spec=Message)
    mock_reply.from_user = MagicMock(spec=User)
    mock_reply.from_user.is_bot = True
    mock_message.reply_to_message = mock_reply

    # Run handler
    await process_city(mock_message, mock_state)

    # Verify user saved
    mock_storage.set_user.assert_called_once()
    saved_args = mock_storage.set_user.call_args[1]
    assert saved_args["city"] == "Paris"
    assert saved_args["timezone"] == "Europe/Paris"
    assert saved_args["platform"] == "telegram"

    # Verify success reply
    mock_message.answer.assert_called_once()
    assert "Set Test: Paris 🇫🇷 (Europe/Paris)" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_time_mention_success(mock_storage_and_cache, mock_message, mock_state, monkeypatch):
    """Test full flow: message -> LLM trigger -> conversion reply."""
    # Mock get_user_cached
    mock_cache = AsyncMock()
    mock_cache.return_value = {
        "city": "Berlin",
        "timezone": "Europe/Berlin",
        "flag": "🇩🇪"
    }
    monkeypatch.setattr("src.commands.common.get_user_cached", mock_cache)
    
    # Mock event_detection.process_message
    mock_process = AsyncMock()
    mock_process.return_value = {
        "event": True,
        "time": ["15:00"],
        "city": [None]
    }
    monkeypatch.setattr("src.commands.common.process_message", mock_process)
    
    # Input message
    mock_message.text = "Let's meet at 15:00"
    mock_message.date = MagicMock()
    mock_message.date.isoformat.return_value = "2026-03-05T10:00:00"
    
    # Run handler
    await handle_time_mention(mock_message, mock_state, skip_aging=True)
    
    # Verify processing
    # 1. process_message called?
    mock_process.assert_called_once()
    
    # Verify send_fn is passed
    kwargs = mock_process.call_args.kwargs
    assert "send_fn" in kwargs
    assert kwargs["send_fn"] is not None
