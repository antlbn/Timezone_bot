"""
Tests for Discord on_message event handler.

Covers:
- Lazy onboarding trigger (time detected, user not registered)
- Registered user flow (send_fn passed, no onboarding)
- Bot message is ignored
- DM (non-guild) message is ignored
- LLM pipeline exception is caught and logged
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord


@pytest.fixture
def mock_message():
    """Create a realistic mock Discord Message."""
    message = MagicMock(spec=discord.Message)

    # Author
    message.author = MagicMock()
    message.author.id = 12345
    message.author.display_name = "TestUser"
    message.author.bot = False

    # Guild
    message.guild = MagicMock()
    message.guild.id = 9999

    # Channel
    message.channel = MagicMock()
    message.channel.id = 111

    # Content / metadata
    message.content = "Meeting at 15:00!"
    message.id = 777
    message.created_at = MagicMock()
    message.created_at.isoformat = MagicMock(return_value="2026-01-01T12:00:00")

    # reply is async
    message.reply = AsyncMock()

    return message


@pytest.fixture
def mock_storage(monkeypatch):
    storage_mock = AsyncMock()
    monkeypatch.setattr("src.discord.events.storage", storage_mock)
    return storage_mock


@pytest.fixture
def mock_process_message(monkeypatch):
    """Mock the LLM pipeline."""
    process_mock = AsyncMock(return_value={"event": None, "points": []})
    monkeypatch.setattr("src.discord.events.process_message", process_mock)
    return process_mock


@pytest.fixture
def mock_get_user_cached(monkeypatch):
    """Mock user cache lookup — returns None (unregistered) by default."""
    cache_mock = AsyncMock(return_value=None)
    monkeypatch.setattr("src.discord.events.get_user_cached", cache_mock)
    return cache_mock


class TestOnMessageBotFilter:
    """Guard conditions: bots and DMs are always ignored."""

    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self, mock_message, mock_storage, mock_process_message):
        """Bot messages must be silently dropped — no processing at all."""
        from src.discord.events import on_message

        mock_message.author.bot = True
        await on_message(mock_message)

        mock_process_message.assert_not_called()
        mock_storage.update_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_dm_messages(self, mock_message, mock_storage, mock_process_message):
        """Messages outside a guild (DMs) must be silently dropped."""
        from src.discord.events import on_message

        mock_message.guild = None
        await on_message(mock_message)

        mock_process_message.assert_not_called()
        mock_storage.update_activity.assert_not_called()


class TestOnMessageRegisteredUser:
    """Registered user path — send_fn is passed, no onboarding shown."""

    @pytest.mark.asyncio
    async def test_registered_user_triggers_pipeline(
        self, mock_message, mock_storage, mock_process_message, monkeypatch
    ):
        """Registered user: process_message called with send_fn, no onboarding message."""
        from src.discord.events import on_message

        # User has timezone → registered
        monkeypatch.setattr(
            "src.discord.events.get_user_cached",
            AsyncMock(return_value={"timezone": "Europe/Berlin", "city": "Berlin"}),
        )

        await on_message(mock_message)

        mock_process_message.assert_called_once()
        call_kwargs = mock_process_message.call_args[1]

        assert call_kwargs["send_fn"] is not None  # send_fn provided
        assert call_kwargs["platform"] == "discord"
        assert call_kwargs["message_text"] == "Meeting at 15:00!"

        # No onboarding reply sent
        mock_message.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_activity_always_updated(
        self, mock_message, mock_storage, mock_process_message, monkeypatch
    ):
        """Activity timestamp is updated for every non-bot guild message."""
        from src.discord.events import on_message

        monkeypatch.setattr(
            "src.discord.events.get_user_cached",
            AsyncMock(return_value={"timezone": "UTC"}),
        )

        await on_message(mock_message)

        mock_storage.update_activity.assert_called_once_with(12345, "discord")


class TestOnMessageLazyOnboarding:
    """Unregistered user + time event detected → lazy onboarding trigger."""

    @pytest.mark.asyncio
    async def test_lazy_onboarding_shown_when_event_detected(
        self, mock_message, mock_storage, monkeypatch
    ):
        """If user is not registered and LLM detects an event, show onboarding invite."""
        from src.discord.events import on_message
        import src.discord.events as events_module
        import src.discord.ui as ui_module
        import src.config as config_module

        # Unregistered user
        monkeypatch.setattr(
            "src.discord.events.get_user_cached",
            AsyncMock(return_value=None),
        )
        # LLM detects a time event
        monkeypatch.setattr(
            "src.discord.events.process_message",
            AsyncMock(return_value={"event": "meeting", "points": []}),
        )
        # Mock save_pending_message (already in module namespace)
        save_mock = AsyncMock()
        monkeypatch.setattr(events_module, "save_pending_message", save_mock)

        # Mock the lazy-imported symbols inside on_message's if-block
        monkeypatch.setattr(ui_module, "SetTimezoneView", MagicMock(return_value=MagicMock()))
        monkeypatch.setattr(config_module, "get_settings_cleanup_timeout", MagicMock(return_value=60))

        await on_message(mock_message)

        # Onboarding reply sent
        mock_message.reply.assert_called_once()
        reply_kwargs = mock_message.reply.call_args[1]
        assert reply_kwargs.get("mention_author") is True

        # Pending message saved with correct user_id and platform
        save_mock.assert_called_once()
        saved_user_id, saved_platform, saved_data = save_mock.call_args[0]
        assert saved_user_id == 12345
        assert saved_platform == "discord"
        assert saved_data["text"] == "Meeting at 15:00!"
        assert saved_data["channel_id"] == "111"

    @pytest.mark.asyncio
    async def test_no_onboarding_when_no_event(
        self, mock_message, mock_storage, monkeypatch
    ):
        """If LLM finds no event, unregistered user does NOT get onboarding invite."""
        from src.discord.events import on_message

        monkeypatch.setattr(
            "src.discord.events.get_user_cached",
            AsyncMock(return_value=None),
        )
        # No event detected
        monkeypatch.setattr(
            "src.discord.events.process_message",
            AsyncMock(return_value={"event": None, "points": []}),
        )

        await on_message(mock_message)

        mock_message.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_fn_not_passed_for_unregistered_user(
        self, mock_message, mock_storage, monkeypatch
    ):
        """Unregistered users: send_fn must be None so the bot doesn't reply inline."""
        from src.discord.events import on_message

        monkeypatch.setattr(
            "src.discord.events.get_user_cached",
            AsyncMock(return_value=None),
        )

        process_mock = AsyncMock(return_value={"event": None, "points": []})
        monkeypatch.setattr("src.discord.events.process_message", process_mock)

        await on_message(mock_message)

        call_kwargs = process_mock.call_args[1]
        assert call_kwargs["send_fn"] is None  # No send_fn for unregistered


class TestOnMessageExceptionHandling:
    """LLM pipeline failures are caught and logged; message handler does not crash."""

    @pytest.mark.asyncio
    async def test_pipeline_exception_is_caught(
        self, mock_message, mock_storage, monkeypatch
    ):
        """If process_message raises, the exception is logged and handler returns cleanly."""
        from src.discord.events import on_message

        monkeypatch.setattr(
            "src.discord.events.get_user_cached",
            AsyncMock(return_value={"timezone": "UTC"}),
        )
        monkeypatch.setattr(
            "src.discord.events.process_message",
            AsyncMock(side_effect=RuntimeError("LLM timeout")),
        )

        mock_logger = MagicMock()
        monkeypatch.setattr("src.discord.events.logger", mock_logger)

        # Should NOT raise
        await on_message(mock_message)

        mock_logger.error.assert_called_once()
        error_msg = mock_logger.error.call_args[0][0]
        assert "Error processing message" in error_msg

    @pytest.mark.asyncio
    async def test_pipeline_exception_does_not_send_reply(
        self, mock_message, mock_storage, monkeypatch
    ):
        """If pipeline crashes, no reply is sent to the channel."""
        from src.discord.events import on_message

        monkeypatch.setattr(
            "src.discord.events.get_user_cached",
            AsyncMock(return_value={"timezone": "UTC"}),
        )
        monkeypatch.setattr(
            "src.discord.events.process_message",
            AsyncMock(side_effect=RuntimeError("timeout")),
        )

        await on_message(mock_message)

        mock_message.reply.assert_not_called()
