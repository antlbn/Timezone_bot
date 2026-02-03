from src.config import PROJECT_ROOT
from src.storage.sqlite import SQLiteStorage

# Singleton instance
storage = SQLiteStorage(PROJECT_ROOT / "data" / "bot.db")

__all__ = ["storage"]
