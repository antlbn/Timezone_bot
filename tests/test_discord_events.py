"""Tests for Discord event handlers, specifically auto-cleanup logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock
import discord


class TestAutoCleanup:
    """Tests for auto-cleanup of stale members during time conversion."""
    
    @pytest.fixture
    def mock_message(self):
        """Create a mock Discord Message."""
        message = MagicMock(spec=discord.Message)
        
        # Author
        message.author = MagicMock()
        message.author.bot = False
        message.author.id = 12345
        message.author.display_name = "TestUser"
        
        # Guild
        message.guild = MagicMock()
        message.guild.id = 9999
        
        # Content with time
        message.content = "Let's meet at 15:00"
        
        # Reply
        message.reply = AsyncMock()
        
        return message
    
    @pytest.fixture
    def mock_storage(self, monkeypatch):
        """Mock the storage singleton."""
        storage_mock = AsyncMock()
        monkeypatch.setattr("src.discord.events.storage", storage_mock)
        return storage_mock
    
    @pytest.fixture
    def mock_formatter(self, monkeypatch):
        """Mock the formatter."""
        formatter_mock = MagicMock()
        formatter_mock.format_conversion_reply.return_value = "Converted times..."
        monkeypatch.setattr("src.discord.events.formatter", formatter_mock)
        return formatter_mock
    
    @pytest.mark.asyncio
    async def test_stale_member_removed(self, mock_message, mock_storage, mock_formatter, monkeypatch):
        """Test that stale members (not in guild) are removed from DB."""
        # Import after mocking
        from src.discord.events import on_message
        
        # Setup: sender is registered
        mock_storage.get_user.return_value = {
            "city": "Berlin",
            "timezone": "Europe/Berlin",
            "flag": "🇩🇪"
        }
        
        # Setup: two members in DB, but only one is still in guild
        mock_storage.get_chat_members.return_value = [
            {"user_id": 12345, "city": "Berlin", "timezone": "Europe/Berlin", "flag": "🇩🇪"},
            {"user_id": 99999, "city": "London", "timezone": "Europe/London", "flag": "🇬🇧"},  # Stale!
        ]
        
        # Mock guild.get_member: returns member for 12345, None for 99999
        def get_member(user_id):
            if user_id == 12345:
                return MagicMock()  # Active member
            return None  # Stale member
        
        mock_message.guild.get_member = get_member
        
        # Mock capture to return time
        monkeypatch.setattr("src.discord.events.capture.extract_times", lambda x: ["15:00"])
        
        # Execute
        await on_message(mock_message)
        
        # Verify stale user was removed
        mock_storage.remove_chat_member.assert_called_once_with(
            9999,  # guild_id
            99999,  # stale user_id
            platform="discord"
        )
    
    @pytest.mark.asyncio
    async def test_active_members_kept(self, mock_message, mock_storage, mock_formatter, monkeypatch):
        """Test that active members are NOT removed."""
        from src.discord.events import on_message
        
        # Setup: sender is registered
        mock_storage.get_user.return_value = {
            "city": "Berlin",
            "timezone": "Europe/Berlin",
            "flag": "🇩🇪"
        }
        
        # Setup: all members are still in guild
        mock_storage.get_chat_members.return_value = [
            {"user_id": 12345, "city": "Berlin", "timezone": "Europe/Berlin", "flag": "🇩🇪"},
            {"user_id": 67890, "city": "London", "timezone": "Europe/London", "flag": "🇬🇧"},
        ]
        
        # Mock guild.get_member: both users exist
        mock_message.guild.get_member = lambda uid: MagicMock()  # All exist
        
        # Mock capture
        monkeypatch.setattr("src.discord.events.capture.extract_times", lambda x: ["15:00"])
        
        # Execute
        await on_message(mock_message)
        
        # Verify NO removals
        mock_storage.remove_chat_member.assert_not_called()
        
        # Verify formatter called with both members
        mock_formatter.format_conversion_reply.assert_called_once()
        call_args = mock_formatter.format_conversion_reply.call_args[0]
        members_passed = call_args[4]  # 5th argument is members list
        assert len(members_passed) == 2
    
    @pytest.mark.asyncio
    async def test_all_stale_returns_early(self, mock_message, mock_storage, mock_formatter, monkeypatch):
        """Test that if ALL members are stale, no reply is sent."""
        from src.discord.events import on_message
        
        # Setup: sender is registered
        mock_storage.get_user.return_value = {
            "city": "Berlin",
            "timezone": "Europe/Berlin",
            "flag": "🇩🇪"
        }
        
        # Setup: one member, but stale
        mock_storage.get_chat_members.return_value = [
            {"user_id": 99999, "city": "London", "timezone": "Europe/London", "flag": "🇬🇧"},
        ]
        
        # All members are stale
        mock_message.guild.get_member = lambda uid: None
        
        # Mock capture
        monkeypatch.setattr("src.discord.events.capture.extract_times", lambda x: ["15:00"])
        
        # Execute
        await on_message(mock_message)
        
        # Verify stale removed
        mock_storage.remove_chat_member.assert_called_once()
        
        # Verify NO reply sent (no active members)
        mock_message.reply.assert_not_called()


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
