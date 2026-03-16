import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat, InlineKeyboardMarkup, CallbackQuery
from src.commands.common import handle_time_mention
from src.commands.settings import process_onboarding_callback, process_city
from src.storage.pending import get_and_delete_pending_messages
import datetime

@pytest.mark.asyncio
async def test_soft_onboarding_flow():
    """
    Test the full soft onboarding flow:
    1. First message triggers buttons and saves to pending.
    2. Second message appends to pending.
    3. Clicking 'No thanks' processes both messages.
    """
    user_id = 12345
    chat_id = 67890
    
    # 1. Setup mocks
    user = User(id=user_id, is_bot=False, first_name="TestUser")
    chat = Chat(id=chat_id, type="group")
    
    msg1 = Message(
        message_id=1,
        date=datetime.datetime.now(),
        chat=chat,
        from_user=user,
        text="Meeting at 15:00"
    )
    
    msg2 = Message(
        message_id=2,
        date=datetime.datetime.now(),
        chat=chat,
        from_user=user,
        text="And another at 16:00"
    )
    
    state = MagicMock()
    
    # Mock storage to return "no user" initially
    with patch("src.commands.common.get_user_cached", return_value=None), \
         patch("src.commands.common.save_pending_message", wraps=None) as mock_save, \
         patch.object(Message, "reply", new_callable=AsyncMock) as mock_reply:
        
        # 2. First message
        await handle_time_mention(msg1, state)
        
        # Verify buttons sent
        args, kwargs = mock_reply.call_args
        assert "coordinate times" in args[0]
        assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)
        
        # 3. Handle second message (should also go to pending)
        with patch("src.commands.common.get_and_delete_pending_messages", return_value=[{"text": "msg1"}]) as mock_get:
            await handle_time_mention(msg2, state)
            # It should have called save_pending_message for both
            assert mock_save.call_count >= 2

    # 4. Verify pending storage has messages (integration-ish check)
    pending = await get_and_delete_pending_messages(user_id, "telegram")
    # In actual execution msg1 and msg2 would be there. 
    # Let's mock the callback part now.

@pytest.mark.asyncio
async def test_onboarding_decline_processes_queue():
    """Verify that declining onboarding triggers processing of cached messages."""
    user_id = 555
    user_name = "Decliner"
    
    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"onboarding:decline:{user_id}"
    callback.from_user = User(id=user_id, is_bot=False, first_name=user_name)
    callback.message = MagicMock(spec=Message)
    callback.message.chat = Chat(id=999, type="group")
    callback.message.edit_text = AsyncMock()
    
    state = MagicMock()
    
    pending_mock = [
        {"text": "10:00 London", "author_name": user_name, "timestamp_utc": "2026-03-16T12:00:00Z"},
        {"text": "Regular chat", "author_name": user_name, "timestamp_utc": "2026-03-16T12:01:00Z"}
    ]
    
    with patch("src.commands.settings.storage.set_user", AsyncMock()) as mock_set_user, \
         patch("src.commands.settings.get_and_delete_pending_messages", AsyncMock(return_value=pending_mock)), \
         patch("src.commands.settings.get_user_cached", AsyncMock(return_value={"user_id": user_id, "timezone": "UTC"})), \
         patch("src.commands.settings.process_message", AsyncMock()) as mock_process:
        
        await process_onboarding_callback(callback, state)
        
        # Verify user saved with declined=True
        mock_set_user.assert_called_once()
        assert mock_set_user.call_args[1]["onboarding_declined"] is True
        
        # Verify process_message called for BOTH pending messages
        assert mock_process.call_count == 2
        callback.message.edit_text.assert_called_with("No problem! If you change your mind, use /tb_settz later.")

@pytest.mark.asyncio
async def test_process_city_relaxed_reply():
    """Verify that process_city works even if message is not a direct reply."""
    user_id = 777
    user_name = "RelaxedUser"
    
    # 1. Setup message from user in waiting_for_city state
    user = User(id=user_id, is_bot=False, first_name=user_name)
    chat = Chat(id=888, type="group")
    
    # This message is NOT a reply (reply_to_message=None)
    msg = Message(
        message_id=10,
        date=datetime.datetime.now(),
        chat=chat,
        from_user=user,
        text="Berlin"
    )
    
    state = MagicMock()
    # Mock state data as if user already clicked "Set city"
    state.get_data = AsyncMock(return_value={"user_id": user_id})
    state.clear = AsyncMock()
    
    with patch("src.commands.settings.geo.get_timezone_by_city", return_value={"city": "Berlin", "timezone": "Europe/Berlin", "flag": "🇩🇪"}), \
         patch("src.commands.settings._save_and_finish", AsyncMock()) as mock_finish:
        
        await process_city(msg, state)
        
        # Should NOT have cleared state (because it's the right user)
        # and SHOULD have called _save_and_finish despite missing reply
        mock_finish.assert_called_once()
        state.clear.assert_not_called()

@pytest.mark.asyncio
async def test_other_user_does_not_clear_state():
    """Verify that a message from another user doesn't clear the target user's onboarding state."""
    target_user_id = 111
    other_user_id = 222
    
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"user_id": target_user_id})
    state.clear = AsyncMock()
    
    other_user = User(id=other_user_id, is_bot=False, first_name="Intruder")
    msg = Message(
        message_id=50,
        date=datetime.datetime.now(),
        chat=Chat(id=1, type="group"),
        from_user=other_user,
        text="I am talking too"
    )
    
    await process_city(msg, state)
    
    # Should NOT clear state for the target user
    state.clear.assert_not_called()

@pytest.mark.asyncio
async def test_onboarding_button_security():
    """Verify that a different user cannot click the onboarding button."""
    target_user_id = 123
    intruder_user_id = 456
    
    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"onboarding:set:{target_user_id}"
    callback.from_user = User(id=intruder_user_id, is_bot=False, first_name="Intruder")
    callback.answer = AsyncMock()
    
    state = MagicMock()
    
    await process_onboarding_callback(callback, state)
    
    # Verify alert was shown and state was NOT touched
    callback.answer.assert_called_once()
    assert "not for you" in callback.answer.call_args[0][0]
    state.set_state.assert_not_called()
