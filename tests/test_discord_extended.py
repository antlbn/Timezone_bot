"""
Tests for remaining uncovered Discord adapter scenarios:

- cmd_members: non-empty list, guild-only guard
- OnboardingMenuView.decline: sets declined status
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

        import src.storage as storage_module
        import src.storage.user_cache as cache_module

        monkeypatch.setattr(storage_module, "storage", storage_mock)
        monkeypatch.setattr(cache_module, "invalidate_user_cache", MagicMock())
        return storage_mock

    @pytest.mark.asyncio
    async def test_decline_sets_declined_status(self, mock_interaction, monkeypatch):
        """Decline saves `onboarding_declined=True` to storage."""
        storage_mock = self._get_mocks(monkeypatch)

        from src.discord.ui import OnboardingMenuView

        view = OnboardingMenuView(target_user_id=12345, guild_id=9999)
        # _ViewCallback is called with just (interaction) from test scope
        await view.decline.callback(mock_interaction)

        storage_mock.set_user.assert_called_once()
        call_kwargs = storage_mock.set_user.call_args[1]
        assert call_kwargs.get("onboarding_declined") is True
        assert call_kwargs.get("user_id") == 12345

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
