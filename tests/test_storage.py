"""Integration tests for storage module."""

import pytest
import os
from pathlib import Path
from src.storage.sqlite import SQLiteStorage

# Temporary database path for testing
TEST_DB = Path(__file__).parent / "test_bot.db"


@pytest.fixture
async def storage():
    """Setup a fresh temporary database and storage instance for each test."""

    def cleanup_files():
        for suffix in ["", "-wal", "-shm"]:
            p = Path(str(TEST_DB) + suffix)
            if p.exists():
                try:
                    os.remove(p)
                except Exception:
                    pass

    cleanup_files()

    _storage = SQLiteStorage(TEST_DB)
    await _storage.init()

    yield _storage

    # Clean up
    await _storage.close()

    # Robust deletion with retry
    import asyncio

    for _ in range(5):
        try:
            for suffix in ["", "-wal", "-shm"]:
                p = Path(str(TEST_DB) + suffix)
                if p.exists():
                    os.remove(p)
        except Exception:
            await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_set_and_get_user(storage):
    """Test setting and retrieving user data."""
    await storage.set_user(123, "telegram", "test_city", "UTC", "🇺🇸", "test_user")

    user = await storage.get_user(123, platform="telegram")
    assert user is not None
    assert user["city"] == "test_city"
    assert user["timezone"] == "UTC"
    assert user["flag"] == "🇺🇸"
    assert user["username"] == "test_user"


@pytest.mark.asyncio
async def test_chat_members(storage):
    """Test adding and retrieving chat members."""
    # First need a user
    await storage.set_user(111, "telegram", "Berlin", "Europe/Berlin", "🇩🇪", "user1")
    await storage.set_user(
        222, "telegram", "New York", "America/New_York", "🇺🇸", "user2"
    )

    # Add to chat
    await storage.add_chat_member(1001, 111, platform="telegram")
    await storage.add_chat_member(1001, 222, platform="telegram")

    members = await storage.get_chat_members(1001, platform="telegram")
    assert len(members) == 2

    # Check if data is correct (joined with users table)
    member_ids = [m["user_id"] for m in members]
    assert 111 in member_ids
    assert 222 in member_ids

    # Check details of one member
    berlin_user = next(m for m in members if m["user_id"] == 111)
    assert berlin_user["city"] == "Berlin"


@pytest.mark.asyncio
async def test_remove_chat_member(storage):
    """Test removing a specific chat member."""
    await storage.set_user(1, "telegram", "A", "UTC", "", "u1")
    await storage.add_chat_member(55, 1, platform="telegram")

    members = await storage.get_chat_members(55, platform="telegram")
    assert len(members) == 1

    await storage.remove_chat_member(55, 1, platform="telegram")
    members = await storage.get_chat_members(55, platform="telegram")
    assert len(members) == 0


@pytest.mark.asyncio
async def test_clear_chat_members(storage):
    """Test clearing all members of a chat."""
    await storage.set_user(1, "telegram", "A", "UTC", "", "u1")
    await storage.set_user(2, "telegram", "B", "UTC", "", "u2")

    await storage.add_chat_member(99, 1, platform="telegram")
    await storage.add_chat_member(99, 2, platform="telegram")

    await storage.clear_chat_members(99, platform="telegram")
    members = await storage.get_chat_members(99, platform="telegram")
    assert len(members) == 0


@pytest.mark.asyncio
async def test_platform_separation(storage):
    """Test that users with same ID on different platforms are separate."""
    # Create user 123 on Telegram
    await storage.set_user(123, "telegram", "Berlin", "Europe/Berlin")

    # Create user 123 on Discord
    await storage.set_user(123, "discord", "New York", "America/New_York")

    # Check Telegram user
    tg_user = await storage.get_user(123, platform="telegram")
    assert tg_user["city"] == "Berlin"

    # Check Discord user
    dc_user = await storage.get_user(123, platform="discord")
    assert dc_user["city"] == "New York"


@pytest.mark.asyncio
async def test_update_user_fields(storage):
    """Test updating existing user data (e.g. city change)."""
    # 1. Create initial user
    await storage.set_user(777, "telegram", "London", "Europe/London", "🇬🇧")

    user_initial = await storage.get_user(777, platform="telegram")
    assert user_initial["city"] == "London"

    # 2. Update user (moved to Paris)
    await storage.set_user(777, "telegram", "Paris", "Europe/Paris", "🇫🇷")

    user_updated = await storage.get_user(777, platform="telegram")
    assert user_updated["city"] == "Paris"
    assert user_updated["timezone"] == "Europe/Paris"
    assert user_updated["flag"] == "🇫🇷"


@pytest.mark.asyncio
async def test_mixed_platform_members(storage):
    """Test that get_chat_members filters by platform correctly."""
    CHAT_ID = 9000

    # User 1 on Telegram
    await storage.set_user(1, "telegram", "T1", "UTC", "T")
    await storage.add_chat_member(CHAT_ID, 1, platform="telegram")

    # User 2 on Discord (Same Chat ID, conceptually)
    await storage.set_user(2, "discord", "D1", "UTC", "D")
    await storage.add_chat_member(CHAT_ID, 2, platform="discord")

    # User 3 on Telegram
    await storage.set_user(3, "telegram", "T2", "UTC", "T")
    await storage.add_chat_member(CHAT_ID, 3, platform="telegram")

    # Get members for Telegram -> Should be [1, 3]
    tg_members = await storage.get_chat_members(CHAT_ID, platform="telegram")
    assert len(tg_members) == 2
    ids = {m["user_id"] for m in tg_members}
    assert ids == {1, 3}

    # Get members for Discord -> Should be [2]
    dc_members = await storage.get_chat_members(CHAT_ID, platform="discord")
    assert len(dc_members) == 1
    assert dc_members[0]["user_id"] == 2


@pytest.mark.asyncio
async def test_sqlite_wal_mode(storage):
    """Verify that SQLite is running in WAL mode."""
    # We check through the storage connection to ensure it's active
    db = await storage._get_conn()
    async with db.execute("PRAGMA journal_mode;") as cursor:
        row = await cursor.fetchone()
        assert row[0].lower() == "wal"
