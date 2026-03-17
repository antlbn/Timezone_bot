import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, Chat, User
from aiogram.fsm.context import FSMContext

from src.commands.states import RemoveMember
from src.commands.members import process_remove

@pytest.fixture
def mock_message():
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 12345
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 12345
    message.answer = AsyncMock()
    return message

@pytest.fixture
def mock_state():
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {
        "user_id": 12345,
        "member_ids": [111, 222, 333]
    }
    return state

@pytest.mark.asyncio
async def test_process_remove_cancel_on_text(mock_message, mock_state, monkeypatch):
    """
    Test that entering standard text instead of a number in the remove flow
    cancels the state and forwards the message to the default handler.
    """
    mock_message.text = "Just a normal chat message 15:00"
    
    # Mock handle_time_mention so we can verify it was called
    mock_handle_time = AsyncMock()
    monkeypatch.setattr("src.commands.common.handle_time_mention", mock_handle_time)
    
    await process_remove(mock_message, mock_state)
    
    # State should be cleared
    mock_state.clear.assert_called_once()
    
    # Should not ask for a number again
    mock_message.answer.assert_not_called()
    
    # Should forward to handle_time_mention
    mock_handle_time.assert_called_once_with(mock_message, mock_state)

@pytest.mark.asyncio
async def test_process_remove_invalid_number(mock_message, mock_state):
    """
    Test that entering an OUT OF BOUNDS number cancels the flow but does NOT
    forward to standard message processing (as it was clearly meant for the bot).
    """
    mock_message.text = "99"
    
    await process_remove(mock_message, mock_state)
    
    # State should be cleared
    mock_state.clear.assert_called_once()
    
    # Should show cancellation alert
    mock_message.answer.assert_called_once()
    assert "Cancelled" in mock_message.answer.call_args[0][0]

from src.commands.settings import process_city, process_fallback_input

@pytest.mark.asyncio
async def test_process_city_invalid_input_prompts_fallback(mock_message, mock_state, monkeypatch):
    """
    Test that entering an invalid city does NOT cancel the flow,
    but instead transitions to waiting_for_time.
    """
    mock_message.text = "Just a normal chat message"
    
    mock_geo = MagicMock()
    mock_geo.get_timezone_by_city.return_value = None
    monkeypatch.setattr("src.commands.settings.geo", mock_geo)
    
    await process_city(mock_message, mock_state)
    
    # State should change to fallback
    mock_state.set_state.assert_called_once()
    args = mock_state.set_state.call_args[0]
    assert "waiting_for_time" in str(args[0])
    
    # Should ask for time playfully
    mock_message.answer.assert_called_once()
    assert "Could not find" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_process_fallback_input_invalid_prompts_again(mock_message, mock_state, monkeypatch):
    """
    Test that entering invalid text in the fallback state prompts again,
    keeping the user in the flow.
    """
    mock_message.text = "Still just a normal message"
    
    mock_geo = MagicMock()
    mock_geo.resolve_timezone_from_input.return_value = None
    monkeypatch.setattr("src.commands.settings.geo", mock_geo)
    
    await process_fallback_input(mock_message, mock_state)
    
    # State should NOT be cleared
    mock_state.clear.assert_not_called()
    
    # Should ask again
    mock_message.answer.assert_called_once()
    assert "Could not find" in mock_message.answer.call_args[0][0]
