import aiosqlite
import time
from pathlib import Path
from ports.storage import StoragePort
from core.domain.enums import Platform
from core.domain.value_objects import UserProfile
import logging

logger = logging.getLogger(__name__)

class SQLiteStorage(StoragePort):
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self._chat_members_cache: dict[tuple[str, Platform], tuple[float, list[UserProfile]]] = {}

    async def initialize(self) -> None:
        await self._get_conn()

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._db is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = await aiosqlite.connect(self.db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.execute("PRAGMA journal_mode=WAL;")
            await self._db.execute("PRAGMA foreign_keys=ON;")
            await self.init_db()
        return self._db

    async def init_db(self):
        if not self._db:
            return
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                platform TEXT,
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
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS chat_members (
                chat_id TEXT,
                user_id INTEGER,
                platform TEXT,
                PRIMARY KEY (chat_id, user_id, platform),
                FOREIGN KEY (user_id, platform) REFERENCES users(user_id, platform) ON DELETE CASCADE
            )
        """)
        await self._db.commit()

    def _row_to_user_profile(self, row: aiosqlite.Row) -> UserProfile:
        return UserProfile(
            user_id=row["user_id"],
            platform=Platform(row["platform"]),
            username=row["username"],
            city=row["city"],
            timezone=row["timezone"],
            flag=row["flag"],
            onboarding_declined=bool(row["onboarding_declined"])
        )

    async def get_user(self, user_id: int, platform: Platform) -> UserProfile | None:
        db = await self._get_conn()
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ? AND platform = ?",
            (user_id, platform.value),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_user_profile(row) if row else None

    async def create_user(self, user_id: int, platform: Platform, author_name: str) -> UserProfile:
        """INSERT for first contact. Returns the inserted profile."""
        db = await self._get_conn()
        async with db.execute(
            """
            INSERT INTO users (user_id, platform, username)
            VALUES (?, ?, ?)
            RETURNING *
            """,
            (user_id, platform.value, author_name),
        ) as cursor:
            row = await cursor.fetchone()
        await db.commit()
        self._chat_members_cache.clear()
        return self._row_to_user_profile(row)

    async def update_username(self, user_id: int, platform: Platform, author_name: str) -> None:
        """Update display name only when it has changed."""
        db = await self._get_conn()
        await db.execute(
            "UPDATE users SET username = ? WHERE user_id = ? AND platform = ?",
            (author_name, user_id, platform.value),
        )
        await db.commit()
        self._chat_members_cache.clear()

    async def ensure_user_metadata(self, user_id: int, platform: Platform, username: str) -> None:
        db = await self._get_conn()
        await db.execute(
            """
            INSERT INTO users (user_id, platform, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, platform) DO UPDATE SET username = excluded.username
            """,
            (user_id, platform.value, username),
        )
        await db.commit()
        self._chat_members_cache.clear()

    async def set_user(self, user_id: int, platform: Platform, timezone: str, city: str | None = None, flag: str | None = None) -> None:
        """Set timezone/city/flag after successful onboarding. Username is managed by ensure_user."""
        db = await self._get_conn()
        await db.execute(
            """
            INSERT INTO users (user_id, platform, city, timezone, flag)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, platform) DO UPDATE SET city = ?, timezone = ?, flag = ?
            """,
            (user_id, platform.value, city, timezone, flag or "", city, timezone, flag or ""),
        )
        await db.commit()
        self._chat_members_cache.clear()

    async def get_chat_members(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        cache_key = (chat_id, platform)
        cached = self._chat_members_cache.get(cache_key)
        now = time.monotonic()
        if cached and cached[0] > now:
            return cached[1]

        db = await self._get_conn()
        async with db.execute(
            """
            SELECT u.*
            FROM chat_members cm
            JOIN users u ON cm.user_id = u.user_id AND cm.platform = u.platform
            WHERE cm.chat_id = ? AND cm.platform = ?
            """,
            (chat_id, platform.value),
        ) as cursor:
            rows = await cursor.fetchall()
            members = [self._row_to_user_profile(row) for row in rows]
            self._chat_members_cache[cache_key] = (now + 60.0, members)
            return members

    async def get_chat_members_with_tz(self, chat_id: str, platform: Platform) -> list[UserProfile]:
        """Fetch only members who have a timezone set. No cache for simplicity for now."""
        db = await self._get_conn()
        async with db.execute(
            """
            SELECT u.*
            FROM chat_members cm
            JOIN users u ON cm.user_id = u.user_id AND cm.platform = u.platform
            WHERE cm.chat_id = ? AND cm.platform = ? AND u.timezone IS NOT NULL
            """,
            (chat_id, platform.value),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_user_profile(row) for row in rows]

    async def add_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        db = await self._get_conn()
        await db.execute(
            "INSERT OR IGNORE INTO chat_members (chat_id, user_id, platform) VALUES (?, ?, ?)",
            (chat_id, user_id, platform.value),
        )
        await db.commit()
        self._chat_members_cache.pop((chat_id, platform), None)

    async def remove_chat_member(self, chat_id: str, user_id: int, platform: Platform) -> None:
        db = await self._get_conn()
        await db.execute(
            "DELETE FROM chat_members WHERE chat_id = ? AND user_id = ? AND platform = ?",
            (chat_id, user_id, platform.value),
        )
        await db.commit()
        self._chat_members_cache.pop((chat_id, platform), None)

    async def update_activity(self, chat_id: str, user_id: int, platform: Platform) -> None:
        db = await self._get_conn()
        await db.execute(
            "UPDATE users SET last_active_at = CURRENT_TIMESTAMP WHERE user_id = ? AND platform = ?",
            (user_id, platform.value),
        )
        await db.commit()

    async def set_onboarding_declined(self, user_id: int, platform: Platform) -> None:
        """Mark as declined. Username was already synced in the message processing flow."""
        db = await self._get_conn()
        await db.execute(
            """
            INSERT INTO users (user_id, platform, onboarding_declined)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, platform) DO UPDATE SET onboarding_declined = 1
            """,
            (user_id, platform.value),
        )
        await db.commit()

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None
