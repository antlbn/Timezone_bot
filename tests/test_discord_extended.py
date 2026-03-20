"""
Tests for remaining uncovered Discord adapter scenarios:

- _process_discord_pending: loop-closure fix, multi-message, pipeline error isolation
- cmd_members: non-empty list, guild-only guard
- OnboardingMenuView.decline: clears pending, sets declined status
- on_guild_remove: storage cleared on bot kick
- cleanup_inactive_users: disabled when days <= 0, runs when enabled
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import discord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_interaction():
    """Reusable mock Discord Interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.user.display_name = "TestUser"
    interaction.guild = MagicMock()
    interaction.guild.id = 9999
    interaction.guild_id = 9999
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.message = None
    return interaction


# ---------------------------------------------------------------------------
# _process_discord_pending
# ---------------------------------------------------------------------------


class TestProcessDiscordPending:
    """Tests for the pending-message processing helper."""

    @pytest.mark.asyncio
    async def test_no_pending_returns_early(self, mock_interaction, monkeypatch):
        """If there are no pending messages, we return immediately without touching process_message."""
        monkeypatch.setattr(
            "src.discord.commands.get_and_delete_pending_messages",
            AsyncMock(return_value=[]),
        )
        process_mock = AsyncMock()
        monkeypatch.setattr("src.discord.commands.process_message", process_mock)

        from src.discord.commands import _process_discord_pending

        await _process_discord_pending(mock_interaction)

        process_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_pending_message_processed(self, mock_interaction, monkeypatch):
        """A single pending message is fully processed with the correct args."""
        pending = {
            "chat_id": "9999",
            "channel_id": "111",
            "text": "Meeting at 15:00",
            "author_name": "Alice",
            "timestamp_utc": "2026-01-01T12:00:00Z",
            "message_id": 777,
            "snapshot": None,
        }
        monkeypatch.setattr(
            "src.discord.commands.get_and_delete_pending_messages",
            AsyncMock(return_value=[pending]),
        )
        monkeypatch.setattr(
            "src.discord.commands.get_user_cached",
            AsyncMock(return_value={"timezone": "Europe/Berlin"}),
        )
        process_mock = AsyncMock()
        monkeypatch.setattr("src.discord.commands.process_message", process_mock)
        # Bot.get_channel returns a working channel
        mock_channel = AsyncMock()
        monkeypatch.setattr("src.discord.commands.bot.get_channel", MagicMock(return_value=mock_channel))

        from src.discord.commands import _process_discord_pending

        await _process_discord_pending(mock_interaction)

        process_mock.assert_called_once()
        call_kwargs = process_mock.call_args[1]
        assert call_kwargs["message_text"] == "Meeting at 15:00"
        assert call_kwargs["skip_history_append"] is True
        assert call_kwargs["skip_aging"] is True

    @pytest.mark.asyncio
    async def test_multiple_pending_all_processed_independently(self, mock_interaction, monkeypatch):
        """Multiple pending messages are each processed; one error doesn't skip the rest."""
        pending_list = [
            {
                "chat_id": "9999", "channel_id": "111", "text": f"msg {i}",
                "author_name": "Alice", "timestamp_utc": "2026-01-01T12:00:00Z",
                "message_id": i, "snapshot": None,
            }
            for i in range(3)
        ]
        monkeypatch.setattr(
            "src.discord.commands.get_and_delete_pending_messages",
            AsyncMock(return_value=pending_list),
        )
        monkeypatch.setattr(
            "src.discord.commands.get_user_cached",
            AsyncMock(return_value={"timezone": "UTC"}),
        )
        monkeypatch.setattr("src.discord.commands.bot.get_channel", MagicMock(return_value=AsyncMock()))

        call_count = 0
        async def process_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("LLM error on second message")

        monkeypatch.setattr("src.discord.commands.process_message", process_side_effect)

        from src.discord.commands import _process_discord_pending

        # Should NOT raise — errors are caught per-message
        await _process_discord_pending(mock_interaction)

        # All 3 attempted despite the middle one failing
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_closure_captures_correct_pending_per_iteration(
        self, mock_interaction, monkeypatch
    ):
        """
        Validates the loop-closure fix: each send_fn must reply to its own channel,
        not always the last pending's channel.
        """
        pending_list = [
            {
                "chat_id": "9999", "channel_id": f"10{i}", "text": f"msg {i}",
                "author_name": "Alice", "timestamp_utc": "2026-01-01T12:00:00Z",
                "message_id": i, "snapshot": None,
            }
            for i in range(2)
        ]
        monkeypatch.setattr(
            "src.discord.commands.get_and_delete_pending_messages",
            AsyncMock(return_value=pending_list),
        )
        monkeypatch.setattr(
            "src.discord.commands.get_user_cached",
            AsyncMock(return_value={"timezone": "UTC"}),
        )

        # Track which channel ids the send_fn calls resolve to
        resolved_channel_ids = []

        def get_channel(channel_id):
            resolved_channel_ids.append(channel_id)
            ch = AsyncMock()
            ch.send = AsyncMock()
            return ch

        monkeypatch.setattr("src.discord.commands.bot.get_channel", get_channel)

        captured_send_fns = []

        async def capture_send_fn(**kwargs):
            captured_send_fns.append(kwargs["send_fn"])

        monkeypatch.setattr("src.discord.commands.process_message", capture_send_fn)

        from src.discord.commands import _process_discord_pending

        await _process_discord_pending(mock_interaction)

        # Now call each captured send_fn and verify it resolves to its own channel
        resolved_channel_ids.clear()
        for fn in captured_send_fns:
            await fn("hello")

        # First fn → channel 100, second fn → channel 101. Not both 101.
        assert resolved_channel_ids == [100, 101], (
            f"Loop closure bug: expected [100, 101], got {resolved_channel_ids}"
        )


# ---------------------------------------------------------------------------
# cmd_members
# ---------------------------------------------------------------------------


class TestCmdMembers:
    """Tests for the /tb_members slash command."""

    @pytest.mark.asyncio
    async def test_members_listed_in_response(self, mock_interaction, monkeypatch):
        """Non-empty member list is rendered and sent."""
        members = [
            {"city": "Berlin", "flag": "🇩🇪", "username": "alice", "timezone": "Europe/Berlin"},
            {"city": "Tokyo", "flag": "🇯🇵", "username": "bob", "timezone": "Asia/Tokyo"},
        ]
        monkeypatch.setattr(
            "src.discord.commands.get_sorted_chat_members",
            AsyncMock(return_value=members),
        )

        from src.discord.commands import cmd_members

        # @bot.tree.command wraps the handler — invoke via .callback
        await cmd_members.callback(mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        text = mock_interaction.response.send_message.call_args[0][0]
        assert "Berlin" in text
        assert "Tokyo" in text
        assert "@alice" in text

    @pytest.mark.asyncio
    async def test_no_guild_shows_error(self, mock_interaction, monkeypatch):
        """/tb_members in a DM shows a guild-only message."""
        mock_interaction.guild = None

        from src.discord.commands import cmd_members

        await cmd_members.callback(mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert call_args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_empty_members_shows_hint(self, mock_interaction, monkeypatch):
        """Empty member list tells user to use /tb_settz."""
        monkeypatch.setattr(
            "src.discord.commands.get_sorted_chat_members",
            AsyncMock(return_value=[]),
        )

        from src.discord.commands import cmd_members

        await cmd_members.callback(mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        text = mock_interaction.response.send_message.call_args[0][0]
        assert "tb_settz" in text


# ---------------------------------------------------------------------------
# OnboardingMenuView.decline
# ---------------------------------------------------------------------------


class TestOnboardingDecline:
    """Tests for the ❌ Decline button in the onboarding menu."""

    def _get_mocks(self, monkeypatch):
        """Shared mock setup for decline button tests."""
        storage_mock = AsyncMock()
        pending_mock = AsyncMock(return_value=[])

        import src.storage as storage_module
        import src.storage.user_cache as cache_module
        import src.storage.pending as pending_module

        monkeypatch.setattr(storage_module, "storage", storage_mock)
        monkeypatch.setattr(cache_module, "invalidate_user_cache", MagicMock())
        monkeypatch.setattr(pending_module, "get_and_delete_pending_messages", pending_mock)
        return storage_mock, pending_mock

    @pytest.mark.asyncio
    async def test_decline_sets_declined_status(self, mock_interaction, monkeypatch):
        """Decline saves `onboarding_declined=True` to storage."""
        storage_mock, _ = self._get_mocks(monkeypatch)

        from src.discord.ui import OnboardingMenuView

        view = OnboardingMenuView(target_user_id=12345, guild_id=9999)
        # _ViewCallback is called with just (interaction) from test scope
        await view.decline.callback(mock_interaction)

        storage_mock.set_user.assert_called_once()
        call_kwargs = storage_mock.set_user.call_args[1]
        assert call_kwargs.get("onboarding_declined") is True
        assert call_kwargs.get("user_id") == 12345

    @pytest.mark.asyncio
    async def test_decline_clears_pending_messages(self, mock_interaction, monkeypatch):
        """Decline removes any pending messages for the user."""
        _, pending_mock = self._get_mocks(monkeypatch)

        from src.discord.ui import OnboardingMenuView

        view = OnboardingMenuView(target_user_id=12345, guild_id=9999)
        await view.decline.callback(mock_interaction)

        pending_mock.assert_called_once_with(12345, "discord")

    @pytest.mark.asyncio
    async def test_decline_edits_message_with_farewell_embed(self, mock_interaction, monkeypatch):
        """After declining, the message is edited to show a farewell embed (view=None)."""
        self._get_mocks(monkeypatch)

        from src.discord.ui import OnboardingMenuView

        view = OnboardingMenuView(target_user_id=12345, guild_id=9999)
        await view.decline.callback(mock_interaction)

        mock_interaction.response.edit_message.assert_called_once()
        call_kwargs = mock_interaction.response.edit_message.call_args[1]
        # View should be None — no more buttons after declining
        assert call_kwargs.get("view") is None
        # Embed should be shown
        assert call_kwargs.get("embed") is not None


# ---------------------------------------------------------------------------
# on_guild_remove
# ---------------------------------------------------------------------------


class TestOnGuildRemove:
    """Tests for the on_guild_remove event handler."""

    @pytest.mark.asyncio
    async def test_guild_members_cleared_on_bot_kick(self, monkeypatch):
        """All guild members are removed from storage when bot is kicked."""
        storage_mock = AsyncMock()
        monkeypatch.setattr("src.discord.events.storage", storage_mock)

        guild = MagicMock(spec=discord.Guild)
        guild.id = 9999

        from src.discord.events import on_guild_remove

        await on_guild_remove(guild)

        storage_mock.clear_chat_members.assert_called_once_with(9999, platform="discord")

    @pytest.mark.asyncio
    async def test_guild_remove_storage_error_is_logged(self, monkeypatch):
        """If storage.clear_chat_members fails, the error is logged (not raised)."""
        storage_mock = AsyncMock()
        storage_mock.clear_chat_members.side_effect = RuntimeError("DB error")
        monkeypatch.setattr("src.discord.events.storage", storage_mock)

        mock_logger = MagicMock()
        monkeypatch.setattr("src.discord.events.logger", mock_logger)

        guild = MagicMock(spec=discord.Guild)
        guild.id = 9999

        from src.discord.events import on_guild_remove

        # Should NOT raise
        await on_guild_remove(guild)

        mock_logger.error.assert_called_once()


# ---------------------------------------------------------------------------
# cleanup_inactive_users (background task)
# ---------------------------------------------------------------------------


class TestCleanupInactiveUsers:
    """Tests for the cleanup_inactive_users background task."""

    @pytest.fixture
    def mock_storage(self, monkeypatch):
        storage_mock = AsyncMock()
        monkeypatch.setattr("src.discord.tasks.storage", storage_mock)
        return storage_mock

    @pytest.fixture
    def mock_bot(self, monkeypatch):
        mock_bot = MagicMock()
        mock_bot.wait_until_ready = AsyncMock()
        monkeypatch.setattr("src.discord.tasks.bot", mock_bot)
        return mock_bot

    @pytest.mark.asyncio
    async def test_cleanup_disabled_when_days_zero(
        self, mock_storage, mock_bot, monkeypatch
    ):
        """When retention_days is 0, no deletion is attempted."""
        monkeypatch.setattr(
            "src.discord.tasks.get_inactive_user_retention_days",
            MagicMock(return_value=0),
        )

        from src.discord.tasks import cleanup_inactive_users

        await cleanup_inactive_users.coro()

        mock_storage.delete_inactive_users.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_runs_when_days_positive(
        self, mock_storage, mock_bot, monkeypatch
    ):
        """When retention_days > 0, delete_inactive_users is called with correct arg."""
        monkeypatch.setattr(
            "src.discord.tasks.get_inactive_user_retention_days",
            MagicMock(return_value=30),
        )
        mock_storage.delete_inactive_users.return_value = 5

        from src.discord.tasks import cleanup_inactive_users

        await cleanup_inactive_users.coro()

        mock_storage.delete_inactive_users.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_cleanup_storage_error_is_caught(
        self, mock_storage, mock_bot, monkeypatch
    ):
        """Storage errors during cleanup are caught and logged, not raised."""
        monkeypatch.setattr(
            "src.discord.tasks.get_inactive_user_retention_days",
            MagicMock(return_value=30),
        )
        mock_storage.delete_inactive_users.side_effect = RuntimeError("DB unavailable")

        mock_logger = MagicMock()
        monkeypatch.setattr("src.discord.tasks.logger", mock_logger)

        from src.discord.tasks import cleanup_inactive_users

        # Should NOT raise
        await cleanup_inactive_users.coro()

        mock_logger.error.assert_called_once()
