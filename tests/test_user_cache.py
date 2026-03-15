
import pytest
from unittest.mock import AsyncMock, patch
from src.storage.user_cache import get_user_cached, invalidate_user_cache, _users_snapshot

@pytest.fixture(autouse=True)
def clear_cache():
    _users_snapshot.clear()

@pytest.mark.asyncio
async def test_get_user_cached_hits_db_first_time():
    """Verify that the first call hits the database and subsequent calls use the cache."""
    mock_user = {"user_id": 1, "platform": "tg", "city": "London", "timezone": "UTC", "flag": "GB"}
    
    with patch("src.storage.storage.get_user", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_user
        
        # 1. First call - should hit DB
        res1 = await get_user_cached(1, "tg")
        assert res1 == mock_user
        assert mock_get.call_count == 1
        
        # 2. Second call - should use cache
        res2 = await get_user_cached(1, "tg")
        assert res2 == mock_user
        assert mock_get.call_count == 1  # Still 1
        assert (1, "tg") in _users_snapshot

@pytest.mark.asyncio
async def test_invalidate_cache():
    """Verify that invalidating the cache forces a re-fetch from the database."""
    mock_user = {"user_id": 1, "platform": "tg", "city": "London"}
    
    with patch("src.storage.storage.get_user", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_user
        
        # Cache the user
        await get_user_cached(1, "tg")
        assert mock_get.call_count == 1
        
        # Invalidate
        invalidate_user_cache(1, "tg")
        assert (1, "tg") not in _users_snapshot
        
        # Call again - should hit DB
        await get_user_cached(1, "tg")
        assert mock_get.call_count == 2
