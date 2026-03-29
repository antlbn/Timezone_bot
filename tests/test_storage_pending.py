import pytest
import asyncio
import datetime
from unittest.mock import AsyncMock, patch
from src.storage.pending import save_pending_message, get_and_delete_pending_messages
from src.event_detection import process_message


@pytest.mark.asyncio
async def test_pending_storage_memory_logic():
    """Verifies in-memory pending storage."""
    platform = "test"
    uid = 101
    await save_pending_message(uid, platform, {"text": "hello"})
    res = await get_and_delete_pending_messages(uid, platform)
    assert len(res) == 1
    assert res[0]["text"] == "hello"
    assert await get_and_delete_pending_messages(uid, platform) == []


@pytest.mark.asyncio
async def test_process_message_calls_detector_without_queue_lock():
    """Current runtime processes messages immediately; chat locks are not part of the entrypoint."""
    with patch(
        "src.event_detection.detect_event", AsyncMock(return_value={"event": True})
    ) as mock_detect:
        result = await process_message(
            "Hello",
            "group_1",
            "u1",
            "telegram",
            "Alice",
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

        assert result.get("event") is True
        mock_detect.assert_called_once()


@pytest.mark.asyncio
async def test_message_aging_skips_before_detector_call():
    """Aging is checked at the entrypoint before detector execution."""
    old_time = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=2)
    ).isoformat()

    with patch("src.event_detection.get_max_message_age", return_value=1):
        with patch("src.event_detection.detect_event", AsyncMock()) as mock_detect:
            result = await process_message(
                "Waiting msg", "group_3", "u1", "telegram", "Alice", old_time
            )

            assert "stale" in result.get("reason", "").lower()
            mock_detect.assert_not_called()
