import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, Chat, User
from aiogram.fsm.context import FSMContext

# Import handlers to test
from src.commands.settings import cmd_me, cmd_settz, process_city
from src.commands.common import handle_time_mention
from src.commands.states import SetTimezone

@pytest.fixture
def mock_storage(monkeypatch):
    """Mock the singleton storage instance."""
    storage_mock = AsyncMock()
    # Apply mock to the module where it is used
    monkeypatch.setattr("src.commands.settings.storage", storage_mock)
    return storage_mock

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
    message.answer = AsyncMock()
    message.reply = AsyncMock()
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
async def test_cmd_me_exists(mock_storage, mock_message):
    """Test /tb_me when user exists in DB."""
    # Setup mock return value
    mock_storage.get_user.return_value = {
        "city": "Berlin",
        "timezone": "Europe/Berlin",
        "flag": "🇩🇪"
    }

    # Run handler
    await cmd_me(mock_message)

    # Verify storage called correctly
    mock_storage.get_user.assert_called_once_with(12345, platform="telegram")
    
    # Verify reply
    mock_message.reply.assert_called_once()
    args, _ = mock_message.reply.call_args
    assert "Berlin 🇩🇪 (Europe/Berlin)" in args[0]

@pytest.mark.asyncio
async def test_cmd_me_not_exists(mock_storage, mock_message):
    """Test /tb_me when user does NOT exist."""
    mock_storage.get_user.return_value = None

    await cmd_me(mock_message)

    # Verify reply
    mock_message.reply.assert_called_once()
    args, _ = mock_message.reply.call_args
    assert "Not set. Use /tb_settz" in args[0]

@pytest.mark.asyncio
async def test_cmd_settz_start(mock_message, mock_state):
    """Test /tb_settz entry point."""
    await cmd_settz(mock_message, mock_state)

    # Verify state set
    mock_state.set_state.assert_called_once_with(SetTimezone.waiting_for_city)
    
    # Verify user data update
    mock_state.update_data.assert_called_once_with(user_id=12345)
    
    # Verify prompt to user
    mock_message.reply.assert_called_once()
    args, _ = mock_message.reply.call_args
    assert "What city are you in?" in args[0]


@pytest.mark.asyncio
async def test_process_city_success(mock_storage, mock_message, mock_state, monkeypatch):
    """Test successful city selection."""
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
async def test_handle_time_mention_success(mock_storage, mock_message, mock_state, monkeypatch):
    """Test full flow: time mention -> conversion reply."""
    # Mock capture (already imported in common, but let's assume input text works with real capture if simple)
    # Actually 'src.commands.common.capture' is a module. Real capture is pure logic, safe to use.
    
    # Mock storage for user
    mock_storage.get_user.return_value = {
        "city": "Berlin",
        "timezone": "Europe/Berlin",
        "flag": "🇩🇪"
    }
    
    # Mock storage for chat members
    mock_storage.get_chat_members.return_value = [
        {"user_id": 12345, "city": "Berlin", "timezone": "Europe/Berlin", "flag": "🇩🇪", "username": "me"},
        {"user_id": 999, "city": "New York", "timezone": "America/New_York", "flag": "🇺🇸", "username": "other"}
    ]
    
    # Mock formatter (to avoid real complex logic if desired, or verify integration)
    # Let's mock it to verify it's CALLED.
    mock_formatter = MagicMock()
    mock_formatter.format_conversion_reply.return_value = "Time in NY: 10:00"
    monkeypatch.setattr("src.commands.common.formatter", mock_formatter)
    
    # Apply storage mock to common.py too (it's a different module import)
    monkeypatch.setattr("src.commands.common.storage", mock_storage)

    # Input message
    mock_message.text = "Let's meet at 15:00"
    
    # Run handler
    await handle_time_mention(mock_message, mock_state)
    
    # Verify processing
    # 1. User fetched?
    mock_storage.get_user.assert_called()
    
    # 2. Members fetched?
    mock_storage.get_chat_members.assert_called_with(mock_message.chat.id, platform="telegram")
    
    # 3. Formatter called?
    mock_formatter.format_conversion_reply.assert_called_once()
    
    # 4. Reply sent?
    mock_message.answer.assert_called_with("Time in NY: 10:00")
