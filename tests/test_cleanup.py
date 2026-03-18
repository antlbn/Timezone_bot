
import pytest
import asyncio
from unittest.mock import patch
from src.storage.pending import save_pending_message, _frozen_messages, cleanup_loop

@pytest.mark.asyncio
async def test_background_cleanup_frozen_messages():
    """Verify that the cleanup_loop actually erases expired messages from memory."""
    _frozen_messages.clear()
    
    # 1. Save two messages: one that will expire, one that stays fresh
    # We'll mock the timeout to be very short (0.1s)
    with patch("src.storage.pending.get_onboarding_timeout", return_value=0.1):
        await save_pending_message(1, "tg", {"text": "to_expire"})
    
    with patch("src.storage.pending.get_onboarding_timeout", return_value=100):
        await save_pending_message(2, "tg", {"text": "stay_fresh"})
    
    assert len(_frozen_messages) == 2
    
    # 2. Trigger one iteration of the cleanup loop
    # We'll wait until the first message expires
    await asyncio.sleep(0.2)
    
    # We patch asyncio.sleep inside the loop to break it after one run
    # or we can just run the logic inside cleanup_loop manually for the test
    # but let's try to run it as a task and cancel it
    
    with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError]):
        try:
            await cleanup_loop()
        except asyncio.CancelledError:
            pass
            
    # 3. Verify results
    assert len(_frozen_messages) == 1
    assert (2, "tg") in _frozen_messages
    assert (1, "tg") not in _frozen_messages
    
    _frozen_messages.clear()
