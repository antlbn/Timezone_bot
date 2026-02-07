
import aiosqlite
from pathlib import Path
from src.logger import get_logger
from src.storage.base import Storage
from typing import List, Dict, Optional

logger = get_logger()

class SQLiteStorage(Storage):
    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def init(self):
        """Initialize database and create tables if not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Users table: Key = (user_id, platform)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER,
                    platform TEXT DEFAULT 'telegram',
                    username TEXT DEFAULT '',
                    city TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    flag TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, platform)
                )
            """)
            
            # Chat members table: Key = (chat_id, user_id, platform)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chat_members (
                    chat_id INTEGER,
                    user_id INTEGER,
                    platform TEXT DEFAULT 'telegram',
                    PRIMARY KEY (chat_id, user_id, platform),
                    FOREIGN KEY (user_id, platform) REFERENCES users(user_id, platform)
                )
            """)
            
            await db.commit()


    async def get_user(self, user_id: int, platform: str) -> Optional[Dict]:
        """Get user by ID and platform."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT user_id, platform, username, city, timezone, flag FROM users WHERE user_id = ? AND platform = ?",
                (user_id, platform)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None


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
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, platform, username, city, timezone, flag)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, platform) DO UPDATE SET username = ?, city = ?, timezone = ?, flag = ?
            """, (user_id, platform, username, city, timezone, flag, username, city, timezone, flag))
            await db.commit()


    async def add_chat_member(self, chat_id: int, user_id: int, platform: str):
        """Register user as member of a chat."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO chat_members (chat_id, user_id, platform)
                VALUES (?, ?, ?)
            """, (chat_id, user_id, platform))
            await db.commit()


    async def get_chat_members(self, chat_id: int, platform: str) -> List[Dict]:
        """Get all users in a chat with their timezone info."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT u.user_id, u.username, u.city, u.timezone, u.flag, u.platform
                FROM chat_members cm
                JOIN users u ON cm.user_id = u.user_id AND cm.platform = u.platform
                WHERE cm.chat_id = ? AND cm.platform = ?
            """, (chat_id, platform)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


    async def remove_chat_member(self, chat_id: int, user_id: int, platform: str):
        """Remove user from chat members."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM chat_members WHERE chat_id = ? AND user_id = ? AND platform = ?",
                (chat_id, user_id, platform)
            )
            await db.commit()


    async def clear_chat_members(self, chat_id: int, platform: str):
        """Remove all members of a chat."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM chat_members WHERE chat_id = ? AND platform = ?",
                (chat_id, platform)
            )
            await db.commit()
