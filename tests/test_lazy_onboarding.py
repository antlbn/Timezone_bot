import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat, CallbackQuery
from src.commands.common import handle_time_mention
from src.commands.settings import dm_decline_callback, process_city
from src.storage.pending import _dm_invite_timestamps
import datetime


@pytest.fixture(autouse=True)
def clean_state():
    _dm_invite_timestamps.clear()
    yield
    _dm_invite_timestamps.clear()


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


@pytest.mark.asyncio
async def test_lazy_no_event_no_invite():
    msg = _make_group_message(text="Hello world")
    state = MagicMock()
    llm_result = {"event": False, "points": []}

    with (
        patch("src.commands.common.get_user_cached", return_value=None),
        patch("src.commands.common.process_message", AsyncMock(return_value=llm_result)) as mock_process,
        patch.object(Message, "reply", new_callable=AsyncMock) as mock_reply,
    ):
        await handle_time_mention(msg, state)
        mock_process.assert_called_once()
        mock_reply.assert_not_called()


@pytest.mark.asyncio
async def test_lazy_event_triggers_invite():
    user_id = 12345
    chat_id = 67890
    msg = _make_group_message(user_id=user_id, chat_id=chat_id, text="Meeting at 15:00")
    state = MagicMock()
    llm_result = {
        "event": True,
        "points": [{"time": "15:00"}],
        "sender_id": str(user_id),
        "sender_name": "TestUser",
    }

    with (
        patch("src.commands.common.get_user_cached", return_value=None),
        patch("src.commands.common.process_message", AsyncMock(return_value=llm_result)),
        patch("src.commands.common.create_start_link", AsyncMock(return_value="https://t.me/bot?start=onboard")),
        patch.object(Message, "reply", new_callable=AsyncMock) as mock_reply,
        patch("src.commands.common.get_dm_onboarding_cooldown", return_value=600),
    ):
        await handle_time_mention(msg, state)
        mock_reply.assert_called_once()
        assert (user_id, "telegram") in _dm_invite_timestamps


@pytest.mark.asyncio
async def test_lazy_decline_clears_cooldown_and_sets_declined():
    user_id = 555
    chat_id = 999
    _dm_invite_timestamps[(user_id, "telegram")] = 123.0

    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"dm_decline:{user_id}:{chat_id}"
    callback.from_user = User(id=user_id, is_bot=False, first_name="Decliner")
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    state = MagicMock()
    state.clear = AsyncMock()

    with patch("src.commands.settings.storage.set_user", AsyncMock()) as mock_set_user:
        await dm_decline_callback(callback, state)
        mock_set_user.assert_called_once()
        assert mock_set_user.call_args[1]["onboarding_declined"] is True
        assert (user_id, "telegram") not in _dm_invite_timestamps


@pytest.mark.asyncio
async def test_successful_onboarding_clears_cooldown_and_saves_timezone():
    user_id = 777
    chat_id = 444
    _dm_invite_timestamps[(user_id, "telegram")] = 123.0
    msg = _make_dm_message(user_id=user_id, text="Berlin")

    state = MagicMock()
    state.get_data = AsyncMock(return_value={"user_id": user_id, "source_chat_id": chat_id})
    state.clear = AsyncMock()

    location = {"city": "Berlin", "timezone": "Europe/Berlin", "flag": "🇩🇪"}

    with (
        patch("src.commands.settings.geo.get_timezone_by_city", return_value=location),
        patch("src.commands.settings.storage.set_user", AsyncMock()) as mock_set,
        patch("src.commands.settings.storage.add_chat_member", AsyncMock()),
        patch.object(Message, "answer", AsyncMock()),
    ):
        await process_city(msg, state)
        mock_set.assert_called_once()
        assert (user_id, "telegram") not in _dm_invite_timestamps
