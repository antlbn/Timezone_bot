import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.event_detection import process_message
from src.event_detection.client import get_chat_llm, reset_llm_cache
from src.event_detection.graph import action_router, llm_node, pre_process_node


@pytest.fixture(autouse=True)
def clear_llm_cache():
    reset_llm_cache()
    yield
    reset_llm_cache()


def test_chat_llm_uses_event_detection_temperature():
    with (
        patch("src.event_detection.client.ChatOpenAI") as mock_cls,
        patch("src.event_detection.client.get_event_detection_temperature", return_value=0.42),
    ):
        get_chat_llm()

    assert mock_cls.call_args.kwargs["temperature"] == 0.42


@pytest.mark.asyncio
async def test_process_message_truncates_soft_limit_before_detector():
    with (
        patch("src.event_detection.detect_event", new_callable=AsyncMock) as mock_detect,
        patch("src.event_detection.get_max_message_length_limit", return_value=12),
    ):
        mock_detect.return_value = {"event": False, "time": [], "city": []}

        await process_message(
            message_text="12345678901234567890",
            chat_id="chat1",
            user_id="u1",
            platform="telegram",
            author_name="John",
            timestamp_utc="2026-03-28T10:00:00Z",
            skip_aging=True,
        )

    assert mock_detect.call_args.kwargs["current_msg"]["text"] == "123456789012"


@pytest.mark.asyncio
async def test_llm_node_uses_human_turn_window_not_message_object_count():
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=AIMessage(content="ok"))

    state = {
        "messages": [
            HumanMessage(content="human-1"),
            AIMessage(content="", tool_calls=[{"name": "publish_event", "args": {}, "id": "tc1"}]),
            ToolMessage(content="published-1", tool_call_id="tc1"),
            HumanMessage(content="human-2"),
            AIMessage(content="", tool_calls=[{"name": "publish_event", "args": {}, "id": "tc2"}]),
            ToolMessage(content="published-2", tool_call_id="tc2"),
            HumanMessage(content="human-3"),
        ]
    }

    with (
        patch("src.event_detection.graph.get_bound_chat_llm", return_value=fake_llm),
        patch("src.config.get_context_messages_limit", return_value=2),
        patch("src.config.get_max_tokens_limit", return_value=10_000),
    ):
        await llm_node(state, {"configurable": {}})

    sent_messages = fake_llm.ainvoke.call_args.args[0]
    assert [m.content for m in sent_messages] == [
        "human-2",
        "",
        "published-2",
        "human-3",
    ]


@pytest.mark.asyncio
async def test_pre_process_node_trims_by_human_turns():
    messages = []
    for idx in range(16):
        tool_call_id = f"tc{idx}"
        human = HumanMessage(content=f"human-{idx}")
        human.id = f"h{idx}"
        ai = AIMessage(content="", tool_calls=[{"name": "publish_event", "args": {}, "id": tool_call_id}])
        ai.id = f"a{idx}"
        tool = ToolMessage(content=f"published-{idx}", tool_call_id=tool_call_id)
        tool.id = f"t{idx}"
        messages.extend([human, ai, tool])

    result = await pre_process_node({"messages": messages}, {"configurable": {}})

    removed_ids = [msg.id for msg in result["messages"]]
    assert removed_ids == ["h0", "a0", "t0"]


def test_action_router_uses_structured_retryable_flag():
    state = {
        "messages": [
            ToolMessage(
                content="Validation failed without relying on string prefixes.",
                tool_call_id="tc1",
                additional_kwargs={"retryable": True},
            )
        ]
    }

    assert action_router(state) == "llm"
