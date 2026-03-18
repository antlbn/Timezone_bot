import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat, CallbackQuery
from src.commands.common import handle_time_mention
from src.commands.settings import (
    dm_decline_callback,
    process_city,
    _handle_expired_messages,
)
from src.storage.pending import _frozen_messages, _dm_invite_timestamps
import datetime
import time as time_mod


def _clear_pending_state():
    """Reset in-memory storage between tests."""
    _frozen_messages.clear()
    _dm_invite_timestamps.clear()


@pytest.fixture(autouse=True)
def clean_state():
    _clear_pending_state()
    yield
    _clear_pending_state()


def _make_group_message(
    user_id=12345, chat_id=67890, text="Meeting at 15:00", msg_id=1
):
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
# 1. Lazy Onboarding: No Event -> No Invite
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lazy_no_event_no_invite():
    """Verify that a message with no time event doesn't trigger onboarding for new users."""
    msg = _make_group_message(text="Hello world")
    state = MagicMock()

    # LLM result with event=False
    llm_result = {"event": False, "points": []}

    with (
        patch("src.commands.common.get_user_cached", return_value=None),
        patch(
            "src.commands.common.process_message", AsyncMock(return_value=llm_result)
        ) as mock_process,
        patch.object(Message, "reply", new_callable=AsyncMock) as mock_reply,
    ):
        await handle_time_mention(msg, state)

        # process_message should be called (Lazy flow)
        mock_process.assert_called_once()
        # No reply (invite) should be sent
        mock_reply.assert_not_called()
        # Nothing should be in pending queue
        assert len(_frozen_messages) == 0


# ---------------------------------------------------------------------------
# 2. Lazy Onboarding: Event -> Invite & Freeze
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lazy_event_triggers_invite():
    """Verify that a time event triggers onboarding and freezes the message."""
    user_id = 12345
    chat_id = 67890
    msg = _make_group_message(user_id=user_id, chat_id=chat_id, text="Meeting at 15:00")
    state = MagicMock()

    # LLM result with event=True
    llm_result = {
        "event": True,
        "points": [{"time": "15:00"}],
        "sender_id": str(user_id),
        "sender_name": "TestUser",
    }

    with (
        patch("src.commands.common.get_user_cached", return_value=None),
        patch(
            "src.commands.common.process_message", AsyncMock(return_value=llm_result)
        ),
        patch(
            "src.commands.common.create_start_link",
            AsyncMock(return_value="https://t.me/bot?start=onboard"),
        ),
        patch.object(Message, "reply", new_callable=AsyncMock) as mock_reply,
        patch("src.commands.common.get_dm_onboarding_cooldown", return_value=600),
    ):
        await handle_time_mention(msg, state)

        # Invite sent
        mock_reply.assert_called_once()
        # Message frozen in pending
        assert (user_id, "telegram") in _frozen_messages
        assert (
            _frozen_messages[(user_id, "telegram")]["messages"][0]["text"]
            == "Meeting at 15:00"
        )


# ---------------------------------------------------------------------------
# 3. Discard on Decline
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lazy_decline_discards_queue():
    """Verify that declining onboarding discards pending messages (Lazy Onboarding Experiment)."""
    user_id = 555
    chat_id = 999

    callback = MagicMock(spec=CallbackQuery)
    callback.data = f"dm_decline:{user_id}:{chat_id}"
    callback.from_user = User(id=user_id, is_bot=False, first_name="Decliner")
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    # Pre-populate pending queue
    _frozen_messages[(user_id, "telegram")] = {
        "messages": [{"text": "Actionable msg", "chat_id": str(chat_id)}],
        "expires": time_mod.time() + 60,
    }

    state = MagicMock()
    state.clear = AsyncMock()

    with (
        patch("src.commands.settings.storage.set_user", AsyncMock()),
        patch("src.commands.settings.process_message", AsyncMock()) as mock_process,
    ):
        await dm_decline_callback(callback, state)

        # Queue should be empty now
        assert (user_id, "telegram") not in _frozen_messages
        # process_message should NOT be called (discarded!)
        mock_process.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Discard on Expiry (Timeout)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lazy_timeout_discards_queue():
    """Verify that expired onboarding messages are discarded (Lazy Onboarding Experiment)."""
    user_id = 888
    platform = "telegram"
    messages = [{"text": "I will be discarded"}]
    bot = MagicMock()

    with (
        patch("src.commands.settings.logger") as mock_logger,
        patch(
            "src.commands.settings._drain_pending_messages", AsyncMock()
        ) as mock_drain,
    ):
        await _handle_expired_messages(bot, user_id, platform, messages)

        # Should log discard and NOT call drain
        mock_drain.assert_not_called()
        # Ensure log mentions discarding
        log_msgs = [call.args[0] for call in mock_logger.info.call_args_list]
        assert any("Discarding" in m for m in log_msgs)


# ---------------------------------------------------------------------------
# 5. Success still converts correctly
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lazy_success_converts_queue():
    """Verify that successful onboarding still converts frozen messages."""
    user_id = 777
    chat_id = 444
    msg = _make_dm_message(user_id=user_id, text="Berlin")

    state = MagicMock()
    state.get_data = AsyncMock(
        return_value={"user_id": user_id, "source_chat_id": chat_id}
    )
    state.clear = AsyncMock()

    _frozen_messages[(user_id, "telegram")] = {
        "messages": [
            {
                "text": "Frozen event",
                "author_name": "User",
                "timestamp_utc": "...",
                "message_id": 1,
                "chat_id": str(chat_id),
            }
        ],
        "expires": time_mod.time() + 60,
    }

    location = {"city": "Berlin", "timezone": "Europe/Berlin", "flag": "🇩🇪"}

    with (
        patch("src.commands.settings.geo.get_timezone_by_city", return_value=location),
        patch("src.commands.settings.storage.set_user", AsyncMock()),
        patch("src.commands.settings.storage.add_chat_member", AsyncMock()),
        patch(
            "src.commands.settings.get_user_cached",
            AsyncMock(return_value={"timezone": "Europe/Berlin"}),
        ),
        patch("src.commands.settings.process_message", AsyncMock()) as mock_process,
        patch.object(Message, "answer", AsyncMock()),
    ):
        await process_city(msg, state)

        # Frozen message should be processed
        mock_process.assert_called_once()
        assert mock_process.call_args[1]["message_text"] == "Frozen event"
        # Queue should be empty
        assert (user_id, "telegram") not in _frozen_messages
