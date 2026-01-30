"""
Storage module.
SQLite operations for users and chat members.
"""
import aiosqlite
from pathlib import Path
from src.config import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "data" / "bot.db"


async def init_db():
    """Initialize database and create tables if not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                city TEXT NOT NULL,
                timezone TEXT NOT NULL,
                flag TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_members (
                chat_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (chat_id, user_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        # Migrations for existing DBs
        try:
            await db.execute("ALTER TABLE users ADD COLUMN flag TEXT DEFAULT ''")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN username TEXT DEFAULT ''")
        except:
            pass
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    """Get user by ID. Returns None if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, city, timezone, flag FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def set_user(user_id: int, city: str, timezone: str, flag: str = "", username: str = ""):
    """Create or update user timezone."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, city, timezone, flag)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = ?, city = ?, timezone = ?, flag = ?
        """, (user_id, username, city, timezone, flag, username, city, timezone, flag))
        await db.commit()


async def add_chat_member(chat_id: int, user_id: int):
    """Register user as member of a chat."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO chat_members (chat_id, user_id)
            VALUES (?, ?)
        """, (chat_id, user_id))
        await db.commit()


async def get_chat_members(chat_id: int) -> list[dict]:
    """Get all users in a chat with their timezone info."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.user_id, u.username, u.city, u.timezone, u.flag
            FROM chat_members cm
            JOIN users u ON cm.user_id = u.user_id
            WHERE cm.chat_id = ?
        """, (chat_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def remove_chat_member(chat_id: int, user_id: int):
    """Remove user from chat members."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM chat_members WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        )
        await db.commit()


async def clear_chat_members(chat_id: int):
    """Remove all members of a chat (e.g. when bot is kicked)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM chat_members WHERE chat_id = ?",
            (chat_id,)
        )
        await db.commit()
