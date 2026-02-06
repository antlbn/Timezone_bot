"""Tests for Discord command handlers."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord


@pytest.fixture
def mock_interaction():
    """Create a mock Discord Interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    
    # User
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.user.display_name = "TestUser"
    
    # Guild
    interaction.guild = MagicMock()
    interaction.guild.id = 9999
    interaction.guild_id = 9999
    
    # Response handling
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.defer = AsyncMock()
    
    # Followup
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    
    return interaction


@pytest.fixture
def mock_storage(monkeypatch):
    """Mock the storage singleton."""
    storage_mock = AsyncMock()
    monkeypatch.setattr("src.discord.commands.storage", storage_mock)
    return storage_mock


class TestHandleSettz:
    """Tests for handle_settz function."""
    
    @pytest.mark.asyncio
    async def test_success_saves_user(self, mock_interaction, mock_storage, monkeypatch):
        """Test successful city lookup saves user and responds."""
        from src.discord.commands import handle_settz
        
        # Mock geo
        mock_geo = MagicMock()
        mock_geo.get_timezone_by_city.return_value = {
            "city": "Berlin",
            "timezone": "Europe/Berlin",
            "flag": "🇩🇪"
        }
        monkeypatch.setattr("src.discord.commands.geo", mock_geo)
        
        await handle_settz(mock_interaction, "Berlin")
        
        # Verify user saved
        mock_storage.set_user.assert_called_once()
        call_kwargs = mock_storage.set_user.call_args[1]
        assert call_kwargs["city"] == "Berlin"
        assert call_kwargs["timezone"] == "Europe/Berlin"
        assert call_kwargs["platform"] == "discord"
        
        # Verify success message
        mock_interaction.followup.send.assert_called()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "Berlin" in msg
        assert "🇩🇪" in msg
    
    @pytest.mark.asyncio
    async def test_city_not_found_shows_fallback(self, mock_interaction, mock_storage, monkeypatch):
        """Test that invalid city shows FallbackView."""
        from src.discord.commands import handle_settz
        
        # Mock geo to return None (city not found)
        mock_geo = MagicMock()
        mock_geo.get_timezone_by_city.return_value = None
        monkeypatch.setattr("src.discord.commands.geo", mock_geo)
        
        await handle_settz(mock_interaction, "InvalidCity123")
        
        # Verify fallback message sent with view
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        
        assert "Could not find" in call_args[0][0]
        assert "view" in call_args[1]  # FallbackView passed
    
    @pytest.mark.asyncio
    async def test_geocoder_error_shows_fallback(self, mock_interaction, mock_storage, monkeypatch):
        """Test that geocoder error shows FallbackView."""
        from src.discord.commands import handle_settz
        
        # Mock geo to return error dict
        mock_geo = MagicMock()
        mock_geo.get_timezone_by_city.return_value = {"error": "Service unavailable"}
        monkeypatch.setattr("src.discord.commands.geo", mock_geo)
        
        await handle_settz(mock_interaction, "Berlin")
        
        # Should show fallback, not crash
        mock_interaction.followup.send.assert_called_once()
        assert "view" in mock_interaction.followup.send.call_args[1]


class TestHandleManualTime:
    """Tests for handle_manual_time function."""
    
    @pytest.mark.asyncio
    async def test_valid_time_saves_user(self, mock_interaction, mock_storage, monkeypatch):
        """Test valid time input resolves and saves user."""
        from src.discord.commands import handle_manual_time
        
        # Mock geo
        mock_geo = MagicMock()
        mock_geo.resolve_timezone_from_input.return_value = {
            "city": "UTC+3",
            "timezone": "Europe/Moscow",
            "flag": "🌐"
        }
        monkeypatch.setattr("src.discord.commands.geo", mock_geo)
        
        await handle_manual_time(mock_interaction, "15:30")
        
        # Verify user saved
        mock_storage.set_user.assert_called_once()
        call_kwargs = mock_storage.set_user.call_args[1]
        assert call_kwargs["timezone"] == "Europe/Moscow"
        assert call_kwargs["platform"] == "discord"
        
        # Verify success message
        mock_interaction.followup.send.assert_called()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "Set:" in msg
    
    @pytest.mark.asyncio
    async def test_invalid_time_shows_fallback(self, mock_interaction, mock_storage, monkeypatch):
        """Test invalid time shows FallbackView."""
        from src.discord.commands import handle_manual_time
        
        # Mock geo to return None (invalid input)
        mock_geo = MagicMock()
        mock_geo.resolve_timezone_from_input.return_value = None
        monkeypatch.setattr("src.discord.commands.geo", mock_geo)
        
        await handle_manual_time(mock_interaction, "invalid")
        
        # Verify fallback shown
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        
        assert "Could not understand" in call_args[0][0]
        assert "view" in call_args[1]


class TestUIComponents:
    """Tests for Discord UI components (Views, Modals)."""
    
    @pytest.mark.asyncio
    async def test_set_timezone_view_has_button(self):
        """Test SetTimezoneView has the expected button."""
        from src.discord.ui import SetTimezoneView
        
        view = SetTimezoneView(target_user_id=12345)
        
        # Should have at least one item (the button)
        assert len(view.children) > 0
        
        # Check target_user_id is stored
        assert view.target_user_id == 12345
    
    @pytest.mark.asyncio
    async def test_fallback_view_has_two_buttons(self):
        """Test FallbackView has 'Try Again' and 'Enter Time' buttons."""
        from src.discord.ui import FallbackView
        
        view = FallbackView(target_user_id=12345)
        
        # Should have 2 buttons
        assert len(view.children) == 2
        
        # Check labels
        labels = [child.label for child in view.children if hasattr(child, 'label')]
        assert "Try Again" in labels
        assert "Enter Time" in labels
    
    @pytest.mark.asyncio
    async def test_view_interaction_check_blocks_other_users(self):
        """Test that views block non-target users."""
        from src.discord.ui import SetTimezoneView
        
        view = SetTimezoneView(target_user_id=12345)
        
        # Create mock interaction from different user
        other_interaction = MagicMock(spec=discord.Interaction)
        other_interaction.user = MagicMock()
        other_interaction.user.id = 99999  # Different user!
        other_interaction.response = MagicMock()
        other_interaction.response.send_message = AsyncMock()
        
        # Should return False (block interaction)
        result = await view.interaction_check(other_interaction)
        
        assert result is False
        other_interaction.response.send_message.assert_called_once()
        # Should have ephemeral=True
        assert other_interaction.response.send_message.call_args[1]["ephemeral"] is True
    
    @pytest.mark.asyncio
    async def test_view_interaction_check_allows_target_user(self):
        """Test that views allow target user."""
        from src.discord.ui import SetTimezoneView
        
        view = SetTimezoneView(target_user_id=12345)
        
        # Create mock interaction from target user
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.id = 12345  # Same user!
        
        # Should return True (allow interaction)
        result = await view.interaction_check(interaction)
        
        assert result is True
