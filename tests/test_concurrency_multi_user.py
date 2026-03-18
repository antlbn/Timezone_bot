import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from aiogram.types import Message, User, Chat
import time as time_mod

# Import targets
from src.commands.common import handle_time_mention
from src.commands.settings import _process_pending_queue_dm
from src.storage.pending import _frozen_messages

def create_mock_message(user_id, user_name, chat_id, text, bot):
    msg = MagicMock(spec=Message)
    msg.chat = MagicMock(spec=Chat)
    msg.chat.id = chat_id
    msg.chat.type = "group"
    msg.from_user = User(id=user_id, is_bot=False, first_name=user_name)
    msg.text = text
    msg.bot = bot
    msg.message_id = 12345
    msg.date = MagicMock()
    msg.date.isoformat.return_value = "2026-03-18T12:00:00"
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg

@pytest.mark.asyncio
async def test_concurrency_multi_user_flow():
    """
    Simulate multiple users in different onboarding states:
    1. Alice: completes setup.
    2. Bob: ignores invite (timeout).
    3. Charlie: starts setup but disappears (timeout).
    4. David: already registered.
    """
    chat_id = -100123
    platform = "telegram"
    bot = MagicMock()
    bot.send_message = AsyncMock()
    
    # Reset storage
    _frozen_messages.clear()
    
    # 1. Setup Mocks
    # David is registered
    mock_users = {
        4: {"user_id": 4, "timezone": "Europe/Paris", "city": "Paris", "flag": "🇫🇷"},
        1: None, # Alice not registered
        2: None, # Bob not registered
        3: None, # Charlie not registered
    }
    
    async def get_user_mock(user_id, platform="telegram"):
        u = mock_users.get(int(user_id))
        return u

    with patch("src.commands.common.get_user_cached", side_effect=get_user_mock), \
         patch("src.commands.common.should_send_dm_invite", return_value=True), \
         patch("src.commands.common.mark_dm_invite_sent", AsyncMock()), \
         patch("src.commands.common.create_start_link", AsyncMock(return_value="https://t.me/bot?start=payload")), \
         patch("src.commands.common.get_settings_cleanup_timeout", return_value=0), \
         patch("src.commands.common.delete_message_after", AsyncMock()), \
         patch("src.commands.common.process_message", AsyncMock(return_value={"event": True, "points": [{"time": "12:00"}]})) as mock_process, \
         patch("src.commands.settings.process_message", new=mock_process), \
         patch("src.commands.settings.get_user_cached", side_effect=get_user_mock):

        # --- STEP 1: All users send messages ---
        
        # David (Registered)
        msg_david = create_mock_message(4, "David", chat_id, "David at 12:00", bot)
        await handle_time_mention(msg_david, MagicMock())
        
        # Alice (New)
        msg_alice = create_mock_message(1, "Alice", chat_id, "Alice at 10:00", bot)
        await handle_time_mention(msg_alice, MagicMock())
        
        # Bob (New)
        msg_bob = create_mock_message(2, "Bob", chat_id, "Bob at 11:00", bot)
        await handle_time_mention(msg_bob, MagicMock())
        
        # Charlie (New)
        msg_charlie = create_mock_message(3, "Charlie", chat_id, "Charlie at 13:00", bot)
        await handle_time_mention(msg_charlie, MagicMock())

        # Lazy: Everyone hits the LLM immediately
        assert mock_process.call_count == 4
        
        assert len(_frozen_messages) == 3 # Alice, Bob, Charlie frozen AFTER LLM detection
        
        # --- STEP 2: Alice completes setup ---
        # Mock Alice registration
        mock_users[1] = {"user_id": 1, "timezone": "Europe/London", "city": "London", "flag": "🇬🇧"}
        
        # Drain Alice's queue (from DM)
        await _process_pending_queue_dm(bot, user_id=1, source_chat_id=chat_id, user_name="Alice")
        
        # VERIFY Alice processed
        # Alice should be the 5th call to process_message (4 initial + 1 release)
        assert mock_process.call_count == 5
        assert mock_process.call_args[1]["author_name"] == "Alice"
        
        # Alice removed from frozen
        assert (1, platform) not in _frozen_messages
        assert len(_frozen_messages) == 2 # Bob, Charlie left
        
        # --- STEP 3: Time passes, Bob and Charlie expire ---
        # Manually expire them
        now = time_mod.time()
        for key in [(2, platform), (3, platform)]:
            _frozen_messages[key]["expires"] = now - 1
            
        # Run cleanup trigger
        from src.storage.pending import cleanup_loop
        
        # Patch sleep to wake up immediately and then break
        with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError()]):
            try:
                await cleanup_loop(bot)
            except asyncio.CancelledError:
                pass
        
        # Give background tasks (asyncio.create_task) a moment to run
        await asyncio.sleep(0.1)
        
        # VERIFY Bob and Charlie discarded by cleanup (No new LLM calls)
        assert mock_process.call_count == 5
        
        # Everyone removed from frozen
        assert len(_frozen_messages) == 0

    print("\n✅ Multi-user concurrency test passed!")
