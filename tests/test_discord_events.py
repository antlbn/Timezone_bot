"""Tests for Discord event handlers, specifically auto-cleanup logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock
import discord


class TestBackgroundSync:
    """Tests for the daily background member sync task."""
    
    @pytest.fixture
    def mock_storage(self, monkeypatch):
        """Mock the storage singleton."""
        storage_mock = AsyncMock()
        monkeypatch.setattr("src.discord.tasks.storage", storage_mock)
        return storage_mock

    @pytest.fixture
    def mock_bot(self, monkeypatch):
        """Mock the bot instance and guilds."""
        mock_bot = MagicMock()
        monkeypatch.setattr("src.discord.tasks.bot", mock_bot)
        return mock_bot

    @pytest.mark.asyncio
    async def test_sync_discord_members_prunes_stale(self, mock_storage, mock_bot, monkeypatch):
        """Test that sync_discord_members prunes members not in guild."""
        from src.discord.tasks import sync_discord_members
        
        # Setup: Mock bot.guilds
        guild = MagicMock()
        guild.id = 9999
        mock_bot.guilds = [guild]
        mock_bot.wait_until_ready = AsyncMock() # Skip wait

        # Setup: members in DB
        mock_storage.get_chat_members.return_value = [
            {"user_id": 12345}, # Active
            {"user_id": 99999}, # Stale
        ]

        # Mock guild.get_member and guild.fetch_member
        def get_member(uid):
            return MagicMock() if uid == 12345 else None
        guild.get_member = get_member
        
        # guild.fetch_member should raise error for 99999
        async def fetch_member(uid):
            if uid == 99999:
                raise Exception("Not found")
            return MagicMock()
        guild.fetch_member = fetch_member

        # Execute
        await sync_discord_members.coro() # Call the underlying coroutine

        # Verify removal called for stale user
        mock_storage.remove_chat_member.assert_called_once_with(9999, 99999, platform="discord")


class TestOnMemberRemove:
    """Tests for on_member_remove event handler."""
    
    @pytest.mark.asyncio
    async def test_member_removed_from_storage(self, monkeypatch):
        """Test that leaving member is removed from storage."""
        from src.discord.events import on_member_remove
        
        # Mock storage
        mock_storage = AsyncMock()
        monkeypatch.setattr("src.discord.events.storage", mock_storage)
        
        # Create mock member
        member = MagicMock(spec=discord.Member)
        member.id = 12345
        member.guild = MagicMock()
        member.guild.id = 9999
        
        # Execute
        await on_member_remove(member)
        
        # Verify removal
        mock_storage.remove_chat_member.assert_called_once_with(
            9999,  # guild_id
            12345,  # user_id
            platform="discord"
        )
