from src.config import PROJECT_ROOT
from src.storage.sqlite import SQLiteStorage

# Singleton instance
storage = SQLiteStorage(PROJECT_ROOT / "data" / "bot.db")

# Helper exports
get_user = storage.get_user
set_user = storage.set_user
add_chat_member = storage.add_chat_member
get_chat_members = storage.get_chat_members
remove_chat_member = storage.remove_chat_member
clear_chat_members = storage.clear_chat_members

__all__ = [
    "storage",
    "get_user",
    "set_user",
    "add_chat_member",
    "get_chat_members",
    "remove_chat_member",
    "clear_chat_members",
]
