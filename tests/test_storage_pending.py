import pytest
import asyncio
import datetime
from unittest.mock import AsyncMock, patch

from src.storage.pending import (
    should_send_dm_invite,
    mark_dm_invite_sent,
    clear_dm_invite,
    _dm_invite_timestamps,
)
from src.event_detection import process_message
from src.event_detection.runtime import get_chat_lock


@pytest.fixture(autouse=True)
def clear_invite_state():
    _dm_invite_timestamps.clear()
    yield
    _dm_invite_timestamps.clear()


@pytest.mark.asyncio
async def test_invite_cooldown_memory_logic():
    assert await should_send_dm_invite(101, "telegram", 600) is True
    await mark_dm_invite_sent(101, "telegram")
    assert await should_send_dm_invite(101, "telegram", 600) is False
    await clear_dm_invite(101, "telegram")
    assert await should_send_dm_invite(101, "telegram", 600) is True


@pytest.mark.asyncio
async def test_waiting_lock_queuing():
    chat_id = "group_1"
    platform = "telegram"
    lock = get_chat_lock(platform, chat_id)

    await lock.acquire()
    try:
        with patch("src.event_detection.detect_event", AsyncMock(return_value={"event": True})) as mock_detect:
            msg_task = asyncio.create_task(
                process_message(
                    "Hello",
                    chat_id,
                    "u1",
                    platform,
                    "Alice",
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                )
            )

            await asyncio.sleep(0.1)
            assert not msg_task.done()
            lock.release()

            result = await msg_task
            assert result.get("event") is True
            mock_detect.assert_called_once()
    finally:
        if lock.locked():
            lock.release()


@pytest.mark.asyncio
async def test_message_aging_while_waiting():
    chat_id = "group_3"
    platform = "telegram"
    lock = get_chat_lock(platform, chat_id)

    fresh_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await lock.acquire()

    try:
        with patch("src.event_detection.get_max_message_age", return_value=1):
            with patch("src.event_detection.detect_event", AsyncMock()) as mock_detect:
                msg_task = asyncio.create_task(
                    process_message("Waiting msg", chat_id, "u1", platform, "Alice", fresh_time)
                )

                await asyncio.sleep(1.5)
                lock.release()

                result = await msg_task
                assert "Message stale after queueing" in result.get("reason")
                mock_detect.assert_not_called()
    finally:
        if lock.locked():
            lock.release()
