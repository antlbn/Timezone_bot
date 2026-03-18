import pytest
import time as time_mod
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from aiogram.types import Message, User, Chat, InlineKeyboardMarkup, CallbackQuery
from src.commands.common import handle_time_mention
from src.commands.settings import dm_onboarding_start, dm_decline_callback, process_city
from src.storage.pending import (
    _frozen_messages, _dm_invite_timestamps,
    save_pending_message, get_and_delete_pending_messages,
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

        # Verify bot asked for city
        mock_answer.assert_called_once()
        assert "city" in mock_answer.call_args[0][0].lower()

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
        {"text": "10:00 London", "author_name": user_name, "timestamp_utc": "2026-03-16T12:00:00Z", "message_id": 1},
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

        # Pending processed
        mock_process.assert_called_once()

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
             {"text": "Meeting at 15:00", "author_name": "TestUser", "timestamp_utc": "2026-03-16T12:00:00Z", "message_id": 1}
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
         patch("src.commands.common.create_start_link", AsyncMock(return_value="https://t.me/bot?start=x")) as mock_link, \
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
