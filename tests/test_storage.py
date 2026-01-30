"""Integration tests for storage module."""
import pytest
import aiosqlite
import os
from pathlib import Path
from src import storage

# Temporary database path for testing
TEST_DB = Path("/Users/johnwunderbellen/Timezone_bot/tests/test_bot.db")

@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Setup a fresh temporary database for each test."""
    # Patch the DB_PATH in storage module
    monkeypatch.setattr(storage, "DB_PATH", TEST_DB)
    
    # Ensure fresh start
    if TEST_DB.exists():
        os.remove(TEST_DB)
    
    # Initialize schema
    await storage.init_db()
    
    yield
    
    # Clean up
    if TEST_DB.exists():
        os.remove(TEST_DB)

@pytest.mark.asyncio
async def test_set_and_get_user():
    """Test setting and retrieving user data."""
    await storage.set_user(123, "test_city", "UTC", "🇺🇸", "test_user")
    
    user = await storage.get_user(123)
    assert user is not None
    assert user["city"] == "test_city"
    assert user["timezone"] == "UTC"
    assert user["flag"] == "🇺🇸"
    assert user["username"] == "test_user"

@pytest.mark.asyncio
async def test_chat_members():
    """Test adding and retrieving chat members."""
    # First need a user
    await storage.set_user(111, "Berlin", "Europe/Berlin", "🇩🇪", "user1")
    await storage.set_user(222, "New York", "America/New_York", "🇺🇸", "user2")
    
    # Add to chat
    await storage.add_chat_member(1001, 111)
    await storage.add_chat_member(1001, 222)
    
    members = await storage.get_chat_members(1001)
    assert len(members) == 2
    
    # Check if data is correct (joined with users table)
    member_ids = [m["user_id"] for m in members]
    assert 111 in member_ids
    assert 222 in member_ids
    
    # Check details of one member
    berlin_user = next(m for m in members if m["user_id"] == 111)
    assert berlin_user["city"] == "Berlin"

@pytest.mark.asyncio
async def test_remove_chat_member():
    """Test removing a specific chat member."""
    await storage.set_user(1, "A", "UTC", "", "u1")
    await storage.add_chat_member(55, 1)
    
    members = await storage.get_chat_members(55)
    assert len(members) == 1
    
    await storage.remove_chat_member(55, 1)
    members = await storage.get_chat_members(55)
    assert len(members) == 0

@pytest.mark.asyncio
async def test_clear_chat_members():
    """Test clearing all members of a chat."""
    await storage.set_user(1, "A", "UTC", "", "u1")
    await storage.set_user(2, "B", "UTC", "", "u2")
    
    await storage.add_chat_member(99, 1)
    await storage.add_chat_member(99, 2)
    
    await storage.clear_chat_members(99)
    members = await storage.get_chat_members(99)
    assert len(members) == 0
