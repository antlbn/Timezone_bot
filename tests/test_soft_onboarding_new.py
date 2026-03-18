import pytest
import asyncio
import time as time_mod
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat, InlineKeyboardMarkup, CallbackQuery
from src.commands.common import handle_time_mention
from src.commands.settings import (
    dm_onboarding_start, dm_decline_callback, process_city,
    dm_change_city_callback, dm_remove_city_callback, 
    dm_extra_settings_callback, dm_back_menu_callback
)
from src.storage.pending import (
    _frozen_messages, _dm_invite_timestamps,
    should_send_dm_invite, mark_dm_invite_sent, clear_dm_invite,
)
import datetime


def _clear_pending_state():
    """Reset in-memory storage between tests."""
    _frozen_messages.clear()
    _dm_invite_timestamps.clear()


@pytest.fixture(autouse=True)
def clean_state():
    _clear_pending_state()
    yield
    _clear_pending_state()


def _make_group_message(user_id=12345, chat_id=67890, text="Meeting at 15:00", msg_id=1):
    user = User(id=user_id, is_bot=False, first_name="TestUser")
    chat = Chat(id=chat_id, type="group")
    return Message(
        message_id=msg_id,
        date=datetime.datetime.now(),
        chat=chat,
        from_user=user,
        text=text,
    )


def _make_dm_message(user_id=12345, text="Berlin", msg_id=10):
    user = User(id=user_id, is_bot=False, first_name="TestUser")
    chat = Chat(id=user_id, type="private")
    return Message(
        message_id=msg_id,
        date=datetime.datetime.now(),
        chat=chat,
        from_user=user,
        text=text,
    )


# ---------------------------------------------------------------------------
# 1. Deep-link URL button is generated in group chat
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dm_onboarding_deep_link_generated():
    """Verify that handle_time_mention sends a URL-button (not callback) for unregistered user."""
    msg = _make_group_message()
    state = MagicMock()

    with patch("src.commands.common.get_user_cached", return_value=None), \
         patch("src.commands.common.create_start_link", AsyncMock(return_value="https://t.me/bot?start=onboard_12345_67890")) as mock_link, \
         patch.object(Message, "reply", new_callable=AsyncMock) as mock_reply, \
         patch("src.commands.common.get_dm_onboarding_cooldown", return_value=600), \
         patch("src.commands.common.get_settings_cleanup_timeout", return_value=10):

        await handle_time_mention(msg, state)

        # Verify reply was sent with URL button
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        assert "timezone" in args[0].lower()

        kb = kwargs["reply_markup"]
        assert isinstance(kb, InlineKeyboardMarkup)
        button = kb.inline_keyboard[0][0]
        # URL button (not callback_data)
        assert button.url is not None
        assert "onboard_12345_67890" in button.url
        assert button.callback_data is None

        # Verify create_start_link was called with correct payload
        mock_link.assert_called_once()
        payload_arg = mock_link.call_args[0][1]
        assert payload_arg == "onboard_12345_67890"


# ---------------------------------------------------------------------------
# 2. DM /start handler sets FSM state
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dm_onboarding_start_handler():
    """Verify /start onboard_123_456 in DM sets FSM to waiting_for_city."""
    user_id = 123
    chat_id = 456

    msg = _make_dm_message(user_id=user_id, text="/start onboard_123_456")
    state = MagicMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()

    command = MagicMock()
    command.args = f"onboard_{user_id}_{chat_id}"

    with patch("src.commands.settings.get_user_cached", AsyncMock(return_value=None)), \
         patch.object(Message, "answer", new_callable=AsyncMock) as mock_answer:

        await dm_onboarding_start(msg, command, state)

        # Verify bot sent the rich welcome message
        mock_answer.assert_called_once()
        text = mock_answer.call_args[0][0]
        assert "What I am" in text
        assert "How to use me" in text
        assert "data" in text.lower()

        # Verify FSM state is NOT set yet (waits for button)
        state.set_state.assert_not_called()
        # But data is saved
        state.update_data.assert_called_once_with(user_id=user_id, source_chat_id=chat_id)


# ---------------------------------------------------------------------------
# 2b. DM "Set my city" button sets FSM state
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dm_setcity_callback():
    """Verify that clicking 'Set my city' in DM sets FSM to waiting_for_city."""
    user_id = 123
    chat_id = 456

    from src.commands.settings import dm_setcity_callback
    
    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"dm_setcity:{user_id}:{chat_id}"
    callback.from_user = User(id=user_id, is_bot=False, first_name="TestUser")
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.answer = AsyncMock()

    state = MagicMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()

    await dm_setcity_callback(callback, state)

    # Verify buttons removed from welcome
    callback.message.edit_reply_markup.assert_called_once_with(reply_markup=None)

    # Verify bot asked for city
    callback.message.answer.assert_called_once()
    assert "your city" in callback.message.answer.call_args[0][0].lower()

    # Verify FSM state set
    from src.commands.states import SetTimezone
    state.set_state.assert_called_once_with(SetTimezone.waiting_for_city)
    state.update_data.assert_called_once_with(user_id=user_id, source_chat_id=chat_id)


# ---------------------------------------------------------------------------
# 3. DM decline sets onboarding_declined and drains queue
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dm_decline_processes_queue():
    """Verify declining in DM saves declined flag and processes pending."""
    user_id = 555
    chat_id = 999
    user_name = "Decliner"

    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"dm_decline:{user_id}:{chat_id}"
    callback.from_user = User(id=user_id, is_bot=False, first_name=user_name)
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.message.bot = AsyncMock()
    callback.answer = AsyncMock()

    state = MagicMock()
    state.clear = AsyncMock()

    pending_mock = [
        {"text": "10:00 London", "author_name": user_name, "timestamp_utc": "2026-03-16T12:00:00Z", "message_id": 1, "chat_id": str(chat_id)},
    ]

    with patch("src.commands.settings.storage.set_user", AsyncMock()) as mock_set_user, \
         patch("src.commands.settings.get_and_delete_pending_messages", AsyncMock(return_value=pending_mock)), \
         patch("src.commands.settings.get_user_cached", AsyncMock(return_value={"user_id": user_id, "timezone": "UTC"})), \
         patch("src.commands.settings.process_message", AsyncMock()) as mock_process, \
         patch("src.commands.settings.clear_dm_invite", AsyncMock()) as mock_clear:

        await dm_decline_callback(callback, state)

        # User saved with declined=True
        mock_set_user.assert_called_once()
        assert mock_set_user.call_args[1]["onboarding_declined"] is True

        # FSM cleared
        state.clear.assert_called_once()

        # Pending discarded (not processed)
        mock_process.assert_not_called()

        # Invite cooldown cleared
        mock_clear.assert_called_once_with(user_id, "telegram")

        # DM message edited
        callback.message.edit_text.assert_called_once()


# ---------------------------------------------------------------------------
# 4. City input in DM saves timezone and drains to source group chat
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dm_city_saves_and_drains():
    """Verify city input in DM saves tz and calls process_message with source chat_id."""
    user_id = 777
    source_chat_id = 888

    msg = _make_dm_message(user_id=user_id, text="Berlin")

    state = MagicMock()
    state.get_data = AsyncMock(return_value={"user_id": user_id, "source_chat_id": source_chat_id})
    state.clear = AsyncMock()

    location = {"city": "Berlin", "timezone": "Europe/Berlin", "flag": "🇩🇪"}

    with patch("src.commands.settings.geo.get_timezone_by_city", return_value=location), \
         patch("src.commands.settings.storage.set_user", AsyncMock()) as mock_set, \
         patch("src.commands.settings.storage.add_chat_member", AsyncMock()), \
         patch("src.commands.settings.invalidate_user_cache") as mock_invalidate, \
         patch("src.commands.settings.get_and_delete_pending_messages", AsyncMock(return_value=[
             {"text": "Meeting at 15:00", "author_name": "TestUser", "timestamp_utc": "2026-03-16T12:00:00Z", "message_id": 1, "chat_id": str(source_chat_id)}
         ])), \
         patch("src.commands.settings.get_user_cached", AsyncMock(return_value={"user_id": user_id, "timezone": "Europe/Berlin"})), \
         patch("src.commands.settings.process_message", AsyncMock()) as mock_process, \
         patch("src.commands.settings.clear_dm_invite", AsyncMock()), \
         patch("src.commands.settings.append_to_history", return_value=[]), \
         patch.object(Message, "answer", new_callable=AsyncMock):

        await process_city(msg, state)

        # User saved with correct timezone
        mock_set.assert_called_once()
        assert mock_set.call_args[1]["timezone"] == "Europe/Berlin"

        # Cache invalidated
        mock_invalidate.assert_called_once_with(user_id, platform="telegram")

        # FSM cleared
        state.clear.assert_called_once()

        # Pending messages processed — sent to source_chat_id, not DM
        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["chat_id"] == str(source_chat_id)


# ---------------------------------------------------------------------------
# 5. DM invite cooldown works
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dm_invite_cooldown():
    """Verify that a second message in group doesn't re-invite if cooldown active."""
    msg1 = _make_group_message(msg_id=1)
    msg2 = _make_group_message(msg_id=2)
    state = MagicMock()

    with patch("src.commands.common.get_user_cached", return_value=None), \
         patch("src.commands.common.create_start_link", AsyncMock(return_value="https://t.me/bot?start=x")), \
         patch.object(Message, "reply", new_callable=AsyncMock) as mock_reply, \
         patch("src.commands.common.get_dm_onboarding_cooldown", return_value=600), \
         patch("src.commands.common.get_settings_cleanup_timeout", return_value=10):

        # First message — invite sent
        await handle_time_mention(msg1, state)
        assert mock_reply.call_count == 1

        # Second message — should NOT send another invite (cooldown)
        await handle_time_mention(msg2, state)
        assert mock_reply.call_count == 1  # Still 1, not 2


# ---------------------------------------------------------------------------
# 6. Wrong user can't use someone else's deep link
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dm_onboarding_wrong_user():
    """Verify /start onboard_999_456 from user_id=123 is rejected."""
    target_user_id = 999
    actual_user_id = 123

    msg = _make_dm_message(user_id=actual_user_id, text="/start onboard_999_456")

    state = MagicMock()
    state.set_state = AsyncMock()

    command = MagicMock()
    command.args = f"onboard_{target_user_id}_456"

    with patch.object(Message, "answer", new_callable=AsyncMock) as mock_answer:
        await dm_onboarding_start(msg, command, state)

        # Should show "not for you" and NOT set state
        mock_answer.assert_called_once()
        assert "not for you" in mock_answer.call_args[0][0].lower()
        state.set_state.assert_not_called()


# ---------------------------------------------------------------------------
# 7. Pending storage: DM invite cooldown functions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_should_send_dm_invite_fresh():
    """No prior invite → should send."""
    assert await should_send_dm_invite(1, "telegram", 600) is True


@pytest.mark.asyncio
async def test_should_send_dm_invite_recent():
    """Recent invite → should NOT send."""
    await mark_dm_invite_sent(1, "telegram")
    assert await should_send_dm_invite(1, "telegram", 600) is False


@pytest.mark.asyncio
async def test_should_send_dm_invite_expired():
    """Old invite (past cooldown) → should send."""
    _dm_invite_timestamps[(1, "telegram")] = time_mod.time() - 700
    assert await should_send_dm_invite(1, "telegram", 600) is True


@pytest.mark.asyncio
async def test_clear_dm_invite():
    """Clearing invite allows re-sending."""
    await mark_dm_invite_sent(1, "telegram")
    assert await should_send_dm_invite(1, "telegram", 600) is False
    await clear_dm_invite(1, "telegram")
    assert await should_send_dm_invite(1, "telegram", 600) is True


# ---------------------------------------------------------------------------
# 8. Settings Menu for Registered Users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dm_onboarding_start_registered_shows_menu():
    """Verify /start from already registered user shows Settings Menu."""
    user_id = 123
    chat_id = 456
    
    msg = _make_dm_message(user_id=user_id, text="/start onboard_123_456")
    state = MagicMock()
    
    command = MagicMock()
    command.args = f"onboard_{user_id}_{chat_id}"
    
    existing = {"user_id": user_id, "city": "Paris", "timezone": "Europe/Paris", "flag": "🇫🇷"}
    
    with patch("src.commands.settings.get_user_cached", AsyncMock(return_value=existing)), \
         patch.object(Message, "answer", new_callable=AsyncMock) as mock_answer:
        
        await dm_onboarding_start(msg, command, state)
        
        # Should show current city + "manage settings"
        mock_answer.assert_called_once()
        text = mock_answer.call_args[0][0]
        assert "Europe/Paris" in text
        assert "manage your settings" in text


@pytest.mark.asyncio
async def test_dm_change_city_callback_sets_state():
    """Verify 'Change timezone' button triggers waiting_for_city."""
    user_id = 123
    chat_id = 456
    
    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"dm_change_city:{user_id}:{chat_id}"
    callback.from_user = User(id=user_id, is_bot=False, first_name="Test")
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    
    state = MagicMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    
    await dm_change_city_callback(callback, state)
    
    # State set
    from src.commands.states import SetTimezone
    state.set_state.assert_called_once_with(SetTimezone.waiting_for_city)
    # Message edited to ask for city
    callback.message.edit_text.assert_called_once()
    assert "What city" in callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_dm_remove_city_callback_clears_db():
    """Verify 'Remove timezone' clears city/tz in storage."""
    user_id = 777
    chat_id = 888
    
    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"dm_remove_city:{user_id}:{chat_id}"
    callback.from_user = User(id=user_id, is_bot=False, first_name="Test")
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    
    with patch("src.commands.settings.storage.set_user", AsyncMock()) as mock_set, \
         patch("src.commands.settings.invalidate_user_cache") as mock_invalidate:
        
        await dm_remove_city_callback(callback, MagicMock())
        
        # User saved with city=None, timezone=None
        mock_set.assert_called_once()
        save_kwargs = mock_set.call_args[1]
        assert save_kwargs["city"] is None
        assert save_kwargs["timezone"] is None
        assert save_kwargs["user_id"] == user_id
        
        # Cache invalidated
        mock_invalidate.assert_called_once_with(user_id, platform="telegram")
        # Text updated to confirm removal
        callback.message.edit_text.assert_called_once()
        assert "removed" in callback.message.edit_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_dm_extra_settings_callback():
    """Verify 'More settings' shows stub info."""
    user_id = 123
    chat_id = 456
    
    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"dm_extra_settings:{user_id}:{chat_id}"
    callback.from_user = User(id=user_id, is_bot=False, first_name="Test")
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    
    await dm_extra_settings_callback(callback)
    
    # Text updated to show extra info
    callback.message.edit_text.assert_called_once()
    assert "Additional Settings" in callback.message.edit_text.call_args[0][0]
    # Answer called to dismiss loading
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_dm_back_menu_callback():
    """Verify 'Back to menu' returns to main settings view."""
    user_id = 123
    chat_id = 456
    
    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"dm_back_menu:{user_id}:{chat_id}"
    callback.from_user = User(id=user_id, is_bot=False, first_name="Test")
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    
    existing = {"user_id": user_id, "city": "Berlin", "timezone": "Europe/Berlin"}
    
    with patch("src.commands.settings.get_user_cached", AsyncMock(return_value=existing)):
        await dm_back_menu_callback(callback)
        
        # Should return to "Your timezone is set to..."
        callback.message.edit_text.assert_called_once()
        assert "timezone is set to" in callback.message.edit_text.call_args[0][0].lower()


# ---------------------------------------------------------------------------
# 9. Plain /start (Without Deep Link)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dm_start_plain_registered_shows_menu():
    """Verify /start (no payload) from registered user shows Settings Menu."""
    user_id = 999
    
    msg = _make_dm_message(user_id=user_id, text="/start")
    state = MagicMock()
    
    command = MagicMock()
    command.args = None # No payload
    
    existing = {"user_id": user_id, "city": "London", "timezone": "Europe/London", "flag": "🇬🇧"}
    
    with patch("src.commands.settings.get_user_cached", AsyncMock(return_value=existing)), \
         patch.object(Message, "answer", new_callable=AsyncMock) as mock_answer:
        
        await dm_onboarding_start(msg, command, state)
        
        # Should show menu even without onboard_ payload
        mock_answer.assert_called_once()
        text = mock_answer.call_args[0][0]
        assert "Europe/London" in text
        assert "manage your settings" in text


@pytest.mark.asyncio
async def test_dm_start_plain_new_user_shows_welcome():
    """Verify /start (no payload) from NEW user shows Welcome message."""
    user_id = 888
    
    msg = _make_dm_message(user_id=user_id, text="/start")
    state = MagicMock()
    state.update_data = AsyncMock()
    
    command = MagicMock()
    command.args = None
    
    with patch("src.commands.settings.get_user_cached", AsyncMock(return_value=None)), \
         patch.object(Message, "answer", new_callable=AsyncMock) as mock_answer:
        
        await dm_onboarding_start(msg, command, state)
        
        # Should show Welcome text
        mock_answer.assert_called_once()
        text = mock_answer.call_args[0][0]
        assert "What I am" in text
        
        # State should be updated with chat_id = 0
        state.update_data.assert_called_once()
        args = state.update_data.call_args[1]
        assert args["source_chat_id"] == 0


# ---------------------------------------------------------------------------
# 10. Timeout Processing (Phase 4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_loop_calls_callback_on_expiration():
    """Verify that cleanup_loop triggers the expire callback for old messages."""
    user_id = 555
    platform = "telegram"
    msg_data = {"text": "hello", "chat_id": 444}
    
    # 1. Setup pending message
    from src.storage.pending import _frozen_messages, cleanup_loop, set_on_expire_callback
    _frozen_messages.clear() # Start clean
    
    # Manually insert an expired message
    _frozen_messages[(user_id, platform)] = {
        "messages": [msg_data],
        "expires": time_mod.time() - 10 # expired 10s ago
    }
    
    # 2. Setup mock callback
    mock_cb = AsyncMock()
    set_on_expire_callback(mock_cb)
    
    # 3. Trigger cleanup by running one iteration of the loop logic.
    # We'll use a side_effect to raise CancelledError after 1 call to stop the loop.
    with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError()]):
        try:
            await cleanup_loop(bot=MagicMock())
        except asyncio.CancelledError:
            pass
            
    # 4. Verify
    mock_cb.assert_called_once()
    args = mock_cb.call_args[0]
    assert args[1] == user_id
    assert args[2] == platform
    assert args[3] == [msg_data]
    assert (user_id, platform) not in _frozen_messages


# ---------------------------------------------------------------------------
# 11. Help Menu Polish (Phase 5)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_group_help_shows_invite_link():
    """Verify /tb_help in group chat shows management cmds + DM link."""
    msg = MagicMock(spec=Message)
    msg.chat = MagicMock()  # Use generic mock for chat
    msg.chat.type = "group"
    msg.chat.title = "Test Group"
    msg.reply = AsyncMock()
    msg.bot = MagicMock()
    
    from src.commands.common import cmd_help
    with patch("src.commands.common.create_start_link", AsyncMock(return_value="https://t.me/bot?start=help")):
        await cmd_help(msg)
        
        msg.reply.assert_called_once()
        text = msg.reply.call_args[0][0]
        assert "/tb_members" in text
        assert "/tb_remove" in text
        assert "manage my settings" in msg.reply.call_args[1]["reply_markup"].inline_keyboard[0][0].text.lower()


@pytest.mark.asyncio
async def test_dm_help_shows_all_commands():
    """Verify /tb_help in DM shows full command list."""
    msg = MagicMock(spec=Message)
    msg.chat = MagicMock() # Use generic mock for chat
    msg.chat.type = "private"
    msg.chat.title = None
    msg.answer = AsyncMock()
    
    from src.commands.common import cmd_help
    await cmd_help(msg)
    
    msg.answer.assert_called_once()
    text = msg.answer.call_args[0][0]
    assert "/tb_me" in text
    assert "/tb_settz" in text
    assert "/tb_members" in text


@pytest.mark.asyncio
async def test_dm_extra_settings_documentation():
    """Verify 'More settings' callback shows real documentation."""
    user_id = 123
    chat_id = 456
    
    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"dm_extra_settings:{user_id}:{chat_id}"
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    
    from src.commands.settings import dm_extra_settings_callback
    await dm_extra_settings_callback(callback)
    
    text = callback.message.edit_text.call_args[0][0]
    assert "/tb_members" in text
    assert "/tb_remove" in text
    # Should explain the "30 days" auto-cleanup
    assert "30 days" in text
