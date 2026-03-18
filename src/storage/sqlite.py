import aiosqlite
from pathlib import Path
from src.logger import get_logger
from src.storage.base import Storage
from typing import List, Dict, Optional

logger = get_logger()


class SQLiteStorage(Storage):
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def _get_conn(self) -> aiosqlite.Connection:
        """Get or create shared connection."""
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            self._db.row_factory = aiosqlite.Row
            # Enable WAL and Foreign Keys for the lifetime of this connection
            await self._db.execute("PRAGMA journal_mode=WAL;")
            await self._db.execute("PRAGMA foreign_keys=ON;")
        return self._db

    async def init(self):
        """Initialize database and create tables if not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db = await self._get_conn()

        # Users table: Key = (user_id, platform)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                platform TEXT DEFAULT 'telegram',
                username TEXT DEFAULT '',
                city TEXT,
                timezone TEXT,
                flag TEXT DEFAULT '',
                onboarding_declined INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                FOREIGN KEY (user_id, platform) REFERENCES users(user_id, platform) ON DELETE CASCADE
            )
        """)

        # Migrations
        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )
            logger.debug("Added last_active_at column to users table")
        except aiosqlite.Error as e:
            if "duplicate column name" not in str(e).lower():
                logger.warning(f"Migration error (last_active_at): {e}")

        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN onboarding_declined INTEGER DEFAULT 0"
            )
            logger.debug("Added onboarding_declined column to users table")
        except aiosqlite.Error as e:
            if "duplicate column name" not in str(e).lower():
                logger.warning(f"Migration error (onboarding_declined): {e}")

        await db.commit()

    async def get_user(self, user_id: int, platform: str) -> Optional[Dict]:
        """Get user by ID and platform."""
        db = await self._get_conn()
        async with db.execute(
            "SELECT user_id, platform, username, city, timezone, flag, onboarding_declined FROM users WHERE user_id = ? AND platform = ?",
            (user_id, platform),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def remove_chat_member(self, chat_id: int, user_id: int, platform: str):
        """Remove user from chat members."""
        db = await self._get_conn()
        await db.execute(
            "DELETE FROM chat_members WHERE chat_id = ? AND user_id = ? AND platform = ?",
            (chat_id, user_id, platform),
        )
        await db.commit()

    async def clear_chat_members(self, chat_id: int, platform: str):
        """Remove all members of a chat."""
        db = await self._get_conn()
        await db.execute(
            "DELETE FROM chat_members WHERE chat_id = ? AND platform = ?",
            (chat_id, platform),
        )
        await db.commit()

    async def update_activity(self, user_id: int, platform: str):
        """Update last_active_at for a user."""
        db = await self._get_conn()
        await db.execute(
            "UPDATE users SET last_active_at = CURRENT_TIMESTAMP WHERE user_id = ? AND platform = ?",
            (user_id, platform),
        )
        await db.commit()

    async def delete_inactive_users(self, days: int) -> int:
        """Delete users who haven't been active for N days. Returns count."""
        db = await self._get_conn()
        # First, find user count to return
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE last_active_at < datetime('now', ?)",
            (f"-{days} days",),
        ) as cursor:
            row = await cursor.fetchone()
            count = row[0] if row else 0

        if count > 0:
            await db.execute(
                "DELETE FROM users WHERE last_active_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            await db.commit()
        return count

    async def set_user(
        self,
        user_id: int,
        platform: str,
        city: Optional[str],
        timezone: Optional[str],
        flag: str = "",
        username: str = "",
        onboarding_declined: bool = False,
    ):
        """Create or update user timezone."""
        db = await self._get_conn()
        declined_int = 1 if onboarding_declined else 0
        await db.execute(
            """
            INSERT INTO users (user_id, platform, username, city, timezone, flag, onboarding_declined)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, platform) DO UPDATE SET username = ?, city = ?, timezone = ?, flag = ?, onboarding_declined = ?
        """,
            (
                user_id,
                platform,
                username,
                city,
                timezone,
                flag,
                declined_int,
                username,
                city,
                timezone,
                flag,
                declined_int,
            ),
        )
        await db.commit()

    async def add_chat_member(self, chat_id: int, user_id: int, platform: str):
        """Register user as member of a chat."""
        db = await self._get_conn()
        await db.execute(
            """
            INSERT OR IGNORE INTO chat_members (chat_id, user_id, platform)
            VALUES (?, ?, ?)
        """,
            (chat_id, user_id, platform),
        )
        await db.commit()

    async def get_chat_members(self, chat_id: int, platform: str) -> List[Dict]:
        """Get all users in a chat with their timezone info."""
        db = await self._get_conn()
        async with db.execute(
            """
            SELECT u.user_id, u.username, u.city, u.timezone, u.flag, u.platform
            FROM chat_members cm
            JOIN users u ON cm.user_id = u.user_id AND cm.platform = u.platform
            WHERE cm.chat_id = ? AND cm.platform = ?
        """,
            (chat_id, platform),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def close(self):
        """Close shared connection."""
        if self._db:
            await self._db.close()
            self._db = None
