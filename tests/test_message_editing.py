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
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, RemoveMessage

from src.event_detection import process_message
from src.event_detection.runtime import _chat_locks


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_history():
    """Reset runtime locks between tests."""
    _chat_locks.clear()
    yield
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
    tool_calls_data = [
        {
            "name": name,
            "args": {"points": [{"time": time, "city": None, "event_type": event_type}]},
            "id": f"call_{name}_{time}",
            "type": "tool_call",
        }
    ]
    if name == "update_previous_event":
        tool_calls_data[0]["args"]["event_ref"] = 1
    return AIMessage(content="", tool_calls=tool_calls_data)


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
        patch("src.event_detection.client.ChatOpenAI", mock_llm_cls),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=MOCK_MEMBERS)),
        patch("src.event_detection.graph._generate_event_ref", return_value=1),
        patch("src.config.get_edit_in_place_enabled", return_value=True),
        patch("src.config.get_republish_edited_message_after_distance", return_value=8),
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
        patch("src.event_detection.client.ChatOpenAI", mock_llm_cls),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=MOCK_MEMBERS)),
        patch("src.event_detection.graph._generate_event_ref", return_value=1),
        patch("src.config.get_edit_in_place_enabled", return_value=True),
        patch("src.config.get_republish_edited_message_after_distance", return_value=8),
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
        patch("src.event_detection.client.ChatOpenAI", mock_llm_cls),
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


# ─────────────────────────────────────────────────────────────────────────────
# DELETE + REPUBLISH: edit_in_place=False (production default path)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_and_republish_flow():
    """
    edit_in_place=False is the current production config.
    update_previous_event must:
      1. call delete_fn(original_msg_id)   — remove old message
      2. call send_fn(new_text)            — post a fresh one
    edit_fn must NOT be called at all.
    """
    CHAT_ID = "tg_chat_republish"
    PLATFORM = "telegram"

    resp1 = _make_tool_call("publish_event",         "10:00")
    resp2 = _make_tool_call("update_previous_event", "11:00")
    mock_llm_cls = _make_llm_cls(resp1, resp2)

    sent_messages: list[str] = []
    edited_calls: list = []
    deleted_ids: list[str] = []
    _call_count = 0

    async def send_fn(text: str) -> str:
        nonlocal _call_count
        _call_count += 1
        sent_messages.append(text)
        return "orig_msg_100" if _call_count == 1 else "new_msg_200"

    async def edit_fn(msg_id: str, text: str):
        edited_calls.append((msg_id, text))

    async def delete_fn(msg_id: str):
        deleted_ids.append(msg_id)

    with (
        patch("src.event_detection.client.ChatOpenAI", mock_llm_cls),
        patch("src.storage.storage.get_chat_members", AsyncMock(return_value=MOCK_MEMBERS)),
        patch("src.event_detection.graph._generate_event_ref", return_value=1),
        patch("src.config.get_edit_in_place_enabled", return_value=False),
    ):
        # Msg 1: schedule
        await process_message(
            message_text="встреча завтра в 10",
            chat_id=CHAT_ID, user_id="u1", platform=PLATFORM,
            author_name="Иван", timestamp_utc="2026-03-20T10:00:00Z",
            sender_db=SENDER_DB,
            send_fn=send_fn, edit_fn=edit_fn, delete_fn=delete_fn,
            skip_aging=True,
        )

        # Msg 2: correction
        await process_message(
            message_text="нет давай в 11",
            chat_id=CHAT_ID, user_id="u2", platform=PLATFORM,
            author_name="Петя", timestamp_utc="2026-03-20T10:05:00Z",
            sender_db=SENDER_DB,
            send_fn=send_fn, edit_fn=edit_fn, delete_fn=delete_fn,
            skip_aging=True,
        )

    assert len(edited_calls) == 0, \
        f"edit_fn must NOT be called when edit_in_place=False, got {edited_calls}"
    assert deleted_ids == ["orig_msg_100"], \
        f"delete_fn must be called once with original msg_id, got {deleted_ids}"
    assert len(sent_messages) == 2, \
        f"send_fn must be called twice (publish + republish), got {len(sent_messages)}"
    assert "11:00" in sent_messages[1], \
        f"Republished message must contain updated time '11:00'"

    print(f"\n[Republish] Original:   {sent_messages[0]}")
    print(f"[Republish] Deleted id: {deleted_ids[0]}")
    print(f"[Republish] New msg:    {sent_messages[1]}")


# ─────────────────────────────────────────────────────────────────────────────
# UNIT: _find_event_by_ref — edge case where Tool found but AI has no match
# ─────────────────────────────────────────────────────────────────────────────

def test_find_event_by_ref_returns_minus_one_when_ai_not_found():
    """
    _find_event_by_ref must return (-1, j) when a ToolMessage matches
    event_ref but no AIMessage has a matching tool_call_id.
    This guards against corrupt/unexpected state without crashing.
    """
    from src.event_detection.graph import _find_event_by_ref

    messages = [
        HumanMessage(content="zoom at 3pm"),
        # AIMessage with a DIFFERENT tool_call_id than the TM below
        AIMessage(
            content="", id="ai-orphan",
            tool_calls=[{"name": "publish_event", "args": {"points": []},
                         "id": "call_WRONG", "type": "tool_call"}],
        ),
        ToolMessage(
            content="✅ Event published. event_ref: 9999. Summary: zoom → 15:00",
            tool_call_id="call_MISMATCH",  # ← no AIMessage references this id
            id="tm-orphan",
        ),
    ]
    result = _find_event_by_ref(messages, 9999)

    assert result is not None, "TM was found, so result must not be None"
    assert result == (-1, 2), \
        f"Expected (-1, 2) when AI not found for TM, got {result}"


# ─────────────────────────────────────────────────────────────────────────────
# GUARD: old_ai_idx == -1 must not schedule the current AIMessage for removal
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_guard_prevents_removing_current_ai_when_idx_is_minus_one():
    """
    Regression for the old_ai_idx == -1 bug:
    Before the fix, messages[-1] resolved to the *current* AI update message,
    causing RemoveMessage to corrupt graph state.
    After the fix, only the orphaned ToolMessage is removed (old_tool_idx >= 0).
    The current AIMessage must survive.
    """
    from src.event_detection.graph import _execute_update
    from src.event_detection.runtime import ActionContext

    CURRENT_AI_ID = "ai-current-update"

    # Craft state where TM has event_ref: 9999 but its tool_call_id
    # doesn't match any AIMessage → _find_event_by_ref returns (-1, 2)
    messages = [
        HumanMessage(content="zoom at 3pm"),
        AIMessage(
            content="", id="ai-orphan",
            tool_calls=[{"name": "publish_event", "args": {"points": []},
                         "id": "call_WRONG", "type": "tool_call"}],
        ),
        ToolMessage(
            content="✅ Event published. event_ref: 9999. Summary: zoom → 15:00",
            tool_call_id="call_MISMATCH",
            id="tm-orphan",
            additional_kwargs={"message_id": "msg_old"},
        ),
        HumanMessage(content="actually 4pm"),
        AIMessage(
            content="", id=CURRENT_AI_ID,
            tool_calls=[{
                "name": "update_previous_event",
                "args": {"event_ref": 9999,
                         "points": [{"time": "16:00", "city": None, "event_type": "zoom"}],
                         "comment": ""},
                "id": "call_update",
                "type": "tool_call",
            }],
        ),
    ]
    tool_call = messages[-1].tool_calls[0]

    action_ctx = ActionContext(
        send_fn=AsyncMock(return_value="new_msg"),
        edit_fn=AsyncMock(),
        build_reply_fn=AsyncMock(return_value="formatted reply"),
        chat_id="test_guard",
        sender_registered=True,
    )

    result = await _execute_update(
        messages=messages,
        tool_call=tool_call,
        action_ctx=action_ctx,
        valid_points=[{"time": "16:00", "city": None, "event_type": "zoom"}],
        comment="",
        summary="zoom → 16:00",
    )

    returned = result["messages"]
    remove_ids = {m.id for m in returned if isinstance(m, RemoveMessage)}

    assert CURRENT_AI_ID not in remove_ids, (
        f"Guard failed: current AIMessage '{CURRENT_AI_ID}' was scheduled "
        f"for removal (old_ai_idx == -1 bug). Got RemoveMessage ids: {remove_ids}"
    )
    # The orphaned TM *should* still be cleaned up
    assert "tm-orphan" in remove_ids, \
        "Orphaned ToolMessage must still be removed even when AI is orphaned"
    # And a fresh ToolMessage confirming the update is in the result
    tool_msgs = [m for m in returned if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1 and "event_ref: 9999" in tool_msgs[0].content
