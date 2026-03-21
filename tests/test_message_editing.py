"""
test_message_editing.py — Integration tests for the edit-message flow

Scenario (per platform):
    1. User1 schedules a meeting → agent calls publish_event
       → send_fn() called → returns message_id stored in history
    2. User2 corrects the time → agent calls update_previous_event
       → edit_fn() called with the stored message_id from step 1

Platforms tested: Telegram, Discord (logical layer, not live bot)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.event_detection import process_message
from src.event_detection.history import _message_history, _chat_locks


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_history():
    """Reset in-memory history between tests."""
    _message_history.clear()
    _chat_locks.clear()
    yield
    _message_history.clear()
    _chat_locks.clear()


def _make_llm_cls(*responses):
    """
    Return a mock ChatOpenAI class whose instances respond with the given
    list of responses in order (side_effect) for sequential ainvoke calls.
    """
    mock_with_tools = MagicMock()
    mock_with_tools.ainvoke = AsyncMock(side_effect=list(responses))
    mock_instance = MagicMock()
    mock_instance.bind_tools = MagicMock(return_value=mock_with_tools)
    return MagicMock(return_value=mock_instance)


def _make_tool_call(name: str, time: str, event_type: str = "встреча"):
    """Build a fake LangChain tool_call response for publish/update tool."""
    resp = MagicMock()
    resp.tool_calls = [
        {
            "name": name,
            "args": {"points": [{"time": time, "city": None, "event_type": event_type}]},
            "id": f"call_{name}_{time}",
        }
    ]
    resp.content = ""
    return resp


MOCK_MEMBERS = [
    {"user_id": "u1", "username": "Ivan",  "timezone": "Europe/Berlin", "city": "Berlin", "flag": "🇩🇪"},
    {"user_id": "u2", "username": "Petya", "timezone": "Europe/Berlin", "city": "Berlin", "flag": "🇩🇪"},
]
SENDER_DB = {"timezone": "Europe/Berlin", "city": "Berlin", "flag": "🇩🇪"}


# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM — edit flow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_message_flow_telegram():
    """
    Telegram platform — full edit flow:
      Msg1: Иван says "встреча завтра в 10"
            → agent: publish_event → send_fn("...") → returns "tg_msg_555"
            → history gains BOT record with message_id="tg_msg_555"
      Msg2: Петя says "нет давай в 11"
            → agent: update_previous_event → edit_fn("tg_msg_555", "...11:00...")
    """
    CHAT_ID = "tg_chat_777"
    PLATFORM = "telegram"

    # Two successive LLM responses
    resp1 = _make_tool_call("publish_event",         "10:00")
    resp2 = _make_tool_call("update_previous_event", "11:00")
    mock_llm_cls = _make_llm_cls(resp1, resp2)

    sent_messages: list[str] = []
    edited_calls: list[tuple[str, str]] = []

    async def send_fn(text: str) -> str:
        sent_messages.append(text)
        return "tg_msg_555"                   # ← Telegram message_id

    async def edit_fn(msg_id: str, new_text: str):
        edited_calls.append((msg_id, new_text))

    with (
        patch("src.event_detection.detector.ChatOpenAI", mock_llm_cls),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=MOCK_MEMBERS)),
    ):
        # ── Message 1: schedule ───────────────────────────────────────────────
        await process_message(
            message_text="встреча завтра в 10",
            chat_id=CHAT_ID,
            user_id="u1",
            platform=PLATFORM,
            author_name="Иван",
            timestamp_utc="2026-03-20T10:00:00Z",
            sender_db=SENDER_DB,
            send_fn=send_fn,
            edit_fn=edit_fn,
            skip_aging=True,
        )

        # ── Message 2: correction ─────────────────────────────────────────────
        await process_message(
            message_text="нет давай в 11",
            chat_id=CHAT_ID,
            user_id="u2",
            platform=PLATFORM,
            author_name="Петя",
            timestamp_utc="2026-03-20T10:05:00Z",
            sender_db=SENDER_DB,
            send_fn=send_fn,
            edit_fn=edit_fn,
            skip_aging=True,
        )

    # ── Assertions ────────────────────────────────────────────────────────────
    assert len(sent_messages) == 1, \
        f"publish_event should send exactly 1 new message, got {len(sent_messages)}"

    assert len(edited_calls) == 1, \
        f"update_previous_event should call edit_fn exactly once, got {len(edited_calls)}"

    edited_msg_id, edited_text = edited_calls[0]
    assert edited_msg_id == "tg_msg_555", \
        f"edit_fn must receive BOT's original message_id, got '{edited_msg_id}'"

    # New text should reference 11:00, not 10:00
    assert "11:00" in edited_text, \
        f"Edited message should contain updated time '11:00', got:\n{edited_text}"
    assert "10:00" not in edited_text or "Berlin" in edited_text, \
        "Edited message should not still show old time as a primary conversion"

    print(f"\n[TG] Original publish:  {sent_messages[0]}")
    print(f"[TG] Edited to msg_id={edited_msg_id}:\n{edited_text}")


# ─────────────────────────────────────────────────────────────────────────────
# DISCORD — edit flow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_message_flow_discord():
    """
    Discord platform — full edit flow:
      Msg1: Иван says "sync tomorrow at 10am"
            → agent: publish_event → send_fn("...") → returns "discord_msg_999"
            → history gains BOT record with message_id="discord_msg_999"
      Msg2: Петя says "let's push to 11 instead"
            → agent: update_previous_event → edit_fn("discord_msg_999", "...11:00...")
    """
    CHAT_ID = "discord_guild_42"
    PLATFORM = "discord"

    resp1 = _make_tool_call("publish_event",         "10:00", "sync")
    resp2 = _make_tool_call("update_previous_event", "11:00", "sync")
    mock_llm_cls = _make_llm_cls(resp1, resp2)

    sent_messages: list[str] = []
    edited_calls: list[tuple[str, str]] = []

    async def send_fn(text: str) -> str:
        sent_messages.append(text)
        return "discord_msg_999"              # ← Discord message.id

    async def edit_fn(msg_id: str, new_text: str):
        edited_calls.append((msg_id, new_text))

    with (
        patch("src.event_detection.detector.ChatOpenAI", mock_llm_cls),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=MOCK_MEMBERS)),
    ):
        # ── Message 1: schedule ───────────────────────────────────────────────
        await process_message(
            message_text="sync tomorrow at 10am",
            chat_id=CHAT_ID,
            user_id="u1",
            platform=PLATFORM,
            author_name="Ivan",
            timestamp_utc="2026-03-20T09:00:00Z",
            sender_db=SENDER_DB,
            send_fn=send_fn,
            edit_fn=edit_fn,
            skip_aging=True,
        )

        # ── Message 2: correction ─────────────────────────────────────────────
        await process_message(
            message_text="let's push to 11 instead",
            chat_id=CHAT_ID,
            user_id="u2",
            platform=PLATFORM,
            author_name="Petya",
            timestamp_utc="2026-03-20T09:05:00Z",
            sender_db=SENDER_DB,
            send_fn=send_fn,
            edit_fn=edit_fn,
            skip_aging=True,
        )

    # ── Assertions ────────────────────────────────────────────────────────────
    assert len(sent_messages) == 1, \
        f"publish_event should send exactly 1 new message, got {len(sent_messages)}"

    assert len(edited_calls) == 1, \
        f"update_previous_event should call edit_fn exactly once, got {len(edited_calls)}"

    edited_msg_id, edited_text = edited_calls[0]
    assert edited_msg_id == "discord_msg_999", \
        f"edit_fn must receive BOT's original message_id, got '{edited_msg_id}'"

    assert "11:00" in edited_text, \
        f"Edited message should contain updated time '11:00', got:\n{edited_text}"

    print(f"\n[DC] Original publish:  {sent_messages[0]}")
    print(f"[DC] Edited to msg_id={edited_msg_id}:\n{edited_text}")


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-CHECK: edit_fn NOT called when there is no previous bot message
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_falls_back_to_publish_when_no_history():
    """
    If the agent requests update_previous_event but the history has no BOT
    record (e.g. fresh chat), edit_fn should NOT be called — instead a new
    message is published via send_fn (graceful fallback).
    """
    resp = _make_tool_call("update_previous_event", "15:00")
    mock_llm_cls = _make_llm_cls(resp)

    sent_messages: list[str] = []
    edited_calls: list = []

    async def send_fn(text: str) -> str:
        sent_messages.append(text)
        return "fallback_msg_001"

    async def edit_fn(msg_id: str, text: str):
        edited_calls.append((msg_id, text))

    with (
        patch("src.event_detection.detector.ChatOpenAI", mock_llm_cls),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=MOCK_MEMBERS)),
    ):
        await process_message(
            message_text="встреча в 15:00",
            chat_id="fresh_chat",
            user_id="u1",
            platform="telegram",
            author_name="Иван",
            timestamp_utc="2026-03-20T10:00:00Z",
            sender_db=SENDER_DB,
            send_fn=send_fn,
            edit_fn=edit_fn,
            skip_aging=True,
        )

    # No previous bot message → edit_fn NOT called → fell back to send_fn
    assert len(edited_calls) == 0, "edit_fn must NOT be called when there is no prior BOT message"
    assert len(sent_messages) == 1, "send_fn must be called as fallback"
    print(f"\n[Fallback] Published new: {sent_messages[0]}")
