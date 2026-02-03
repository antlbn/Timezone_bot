from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class Storage(ABC):
    """
    Abstract Interface for Database Storage.
    Supports multi-platform (Telegram, Discord) via 'platform' parameter.
    """

    @abstractmethod
    async def init(self):
        """Initialize database connection and schema."""
        pass

    @abstractmethod
    async def get_user(self, user_id: int, platform: str) -> Optional[Dict]:
        """Get user by ID and platform. Returns None if not found."""
        pass

    @abstractmethod
    async def set_user(
        self, 
        user_id: int, 
        platform: str,
        city: str, 
        timezone: str, 
        flag: str = "", 
        username: str = ""
    ):
        """Create or update user timezone."""
        pass

    @abstractmethod
    async def add_chat_member(self, chat_id: int, user_id: int, platform: str):
        """Register user as member of a chat."""
        pass

    @abstractmethod
    async def get_chat_members(self, chat_id: int, platform: str) -> List[Dict]:
        """Get all users in a chat with their timezone info."""
        pass

    @abstractmethod
    async def remove_chat_member(self, chat_id: int, user_id: int, platform: str):
        """Remove user from chat members."""
        pass

    @abstractmethod
    async def clear_chat_members(self, chat_id: int, platform: str):
        """Remove all members of a chat (e.g. when bot is kicked)."""
        pass
