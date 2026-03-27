"""
graph.py — LangGraph Definition for Timezone Bot
This module defines the StateGraph, nodes, and tools for the event detection loop.
"""

import re
import random
from typing import Annotated, TypedDict
from langchain_core.messages import (
    BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage, RemoveMessage
)
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from src.logger import get_logger
from src.event_detection.client import get_bound_chat_llm
from src.event_detection.runtime import ActionContext, get_action_context
logger = get_logger()

# ── 1. Define State ────────────────────────────────────────────────────────

class GraphState(TypedDict):
    """
    The state of the conversation graph.
    messages: Built-in LangGraph list of messages with reducer (add_messages).
    """
    messages: Annotated[list[BaseMessage], add_messages]


# ── 2. Define Tools Schema ──────────────────────────────────────────────────

class EventPoint(BaseModel):
    time: str | None = Field(default=None, description="HH:MM 24h. Null if no exact time. No guessing.")
    city: str | None = Field(description="City/timezone if mentioned, else null.")
    event_type: str = Field(description="Short event name ('zoom').")

@tool
def publish_event(points: list[EventPoint], comment: str = "") -> str:
    """Create NEW event. Schema-only tool; real execution happens in action_node."""
    raise RuntimeError("Schema-only tool. Execution is implemented in action_node().")

@tool
def update_previous_event(event_ref: int, points: list[EventPoint], comment: str = "") -> str:
    """Update event from history. Schema-only tool; real execution happens in action_node."""
    raise RuntimeError("Schema-only tool. Execution is implemented in action_node().")

tools_list = [publish_event, update_previous_event]


# ── Helpers ─────────────────────────────────────────────────────────────────

def _format_event_summary(points: list[dict]) -> str:
    """Build a short summary string from points for ToolMessage content."""
    parts = []
    for p in points:
        et = p.get("event_type", "event")
        t = p.get("time", "?")
        c = p.get("city")
        parts.append(f"{et} → {t}" + (f" ({c})" if c else ""))
    return ", ".join(parts)



def _generate_event_ref(messages: list) -> int:
    """Generate a unique 4-digit event reference ID."""
    existing_refs = set()
    # Support both "event #1" and "event_ref: 1"
    pattern = re.compile(r"(?:event_ref: |#)(\d+)")
    for m in messages:
        if isinstance(m, ToolMessage) and m.content:
            match = pattern.search(m.content)
            if match:
                existing_refs.add(int(match.group(1)))
                
    while True:
        ref = random.randint(1000, 9999)
        if ref not in existing_refs:
            return ref


def _find_event_by_ref(messages: list, event_ref: int) -> tuple[int, int] | None:
    """Find the (ai_idx, tool_idx) pair for a specific event_ref.
    
    Looks for a ToolMessage with 'event_ref: N' or 'event #N' and then
    finds its corresponding AIMessage.
    Returns indices into the messages list, or None if not found.
    """
    pattern = re.compile(rf"(?:event_ref: |#){event_ref}\b")
    
    # Search backwards to find the latest tool message for this event_ref
    for j in range(len(messages) - 1, -1, -1):
        m = messages[j]
        if isinstance(m, ToolMessage) and m.content and pattern.search(m.content):
            tc_id = m.tool_call_id
            # Now find the AIMessage that generated this tool call
            for i in range(j - 1, -1, -1):
                ai_m = messages[i]
                if isinstance(ai_m, AIMessage) and ai_m.tool_calls:
                    for tc in ai_m.tool_calls:
                        if tc["id"] == tc_id:
                            return (i, j)
            return (-1, j)  # Found tool but not AI (shouldn't happen in normal state)
    return None


def _get_action_context(config: RunnableConfig) -> tuple[str, ActionContext | None]:
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "")
    return thread_id, get_action_context(thread_id)


def _normalize_points(points: list) -> list[dict]:
    time_pattern = re.compile(r"^\d{1,2}:\d{2}$")
    points_dicts = [p.model_dump() if hasattr(p, "model_dump") else p.dict() if hasattr(p, "dict") else p for p in points]
    return [
        p for p in points_dicts
        if isinstance(p, dict)
        and isinstance(p.get("time"), str)
        and time_pattern.match(p["time"].strip())
    ]


def _build_validation_error(tool_call_id: str) -> dict:
    err_msg = (
        "Error: no extractable time found. Do NOT call tools for vague times like "
        "'evening'. If meeting today, give HH:MM format."
    )
    return {"messages": [ToolMessage(content=err_msg, tool_call_id=tool_call_id)]}


def _build_registration_gate(tool_call_id: str, tool_name: str, summary: str) -> dict:
    return {
        "messages": [
            ToolMessage(
                content=(
                    "No event action executed due to app logic. "
                    "Reason: sender not registered; onboarding required. "
                    f"Detected intent: {tool_name}. Summary: {summary}"
                ),
                tool_call_id=tool_call_id,
            )
        ]
    }


async def _send_reply(
    action_ctx: ActionContext,
    points: list[dict],
    comment: str,
) -> str | None:
    if not action_ctx.build_reply_fn:
        return None

    reply = await action_ctx.build_reply_fn(points, comment or None)
    if reply and action_ctx.send_fn:
        return await action_ctx.send_fn(reply)
    return None


async def _execute_publish(
    messages: list,
    tool_call: dict,
    action_ctx: ActionContext,
    valid_points: list[dict],
    comment: str,
    summary: str,
) -> dict:
    event_num = _generate_event_ref(messages)
    message_id = await _send_reply(action_ctx, valid_points, comment)

    tool_output = f"✅ Event published. event_ref: {event_num}. Summary: {summary}"
    if comment:
        tool_output += f". Comment: {comment}"

    return {
        "messages": [
            ToolMessage(
                content=tool_output,
                tool_call_id=tool_call["id"],
                additional_kwargs={"message_id": message_id} if message_id else {},
            )
        ]
    }


async def _apply_update_side_effects(
    messages: list,
    action_ctx: ActionContext,
    valid_points: list[dict],
    comment: str,
    old_ai_idx: int,
    prev_msg_id: str | None,
    event_ref: int,
) -> str | None:
    if not action_ctx.build_reply_fn:
        return None

    reply = await action_ctx.build_reply_fn(valid_points, comment or None)
    if not reply:
        return None

    from src.config import get_republish_edited_message_after_distance, get_edit_in_place_enabled

    distance = sum(1 for m in messages[old_ai_idx:] if isinstance(m, HumanMessage))
    limit = get_republish_edited_message_after_distance()
    edit_enabled = get_edit_in_place_enabled()

    if not edit_enabled or distance > limit:
        logger.info(
            f"[chat:{action_ctx.chat_id}] update event #{event_ref} "
            f"(edit_enabled={edit_enabled}, distance={distance}). Delete+republish."
        )
        if action_ctx.delete_fn and prev_msg_id:
            await action_ctx.delete_fn(prev_msg_id)
        if action_ctx.send_fn:
            return await action_ctx.send_fn(reply)
        return None

    logger.info(
        f"[chat:{action_ctx.chat_id}] update event #{event_ref} {distance} msgs away. Editing in place."
    )
    if action_ctx.edit_fn and prev_msg_id:
        try:
            await action_ctx.edit_fn(prev_msg_id, reply)
            return prev_msg_id
        except Exception as exc:
            logger.warning(f"Edit failed: {exc}. Falling back to publish.")

    if action_ctx.send_fn:
        return await action_ctx.send_fn(reply)
    return None


async def _execute_update(
    messages: list,
    tool_call: dict,
    action_ctx: ActionContext,
    valid_points: list[dict],
    comment: str,
    summary: str,
) -> dict:
    event_ref = tool_call["args"].get("event_ref", 0)
    ref_result = _find_event_by_ref(messages, event_ref)

    if ref_result is None:
        logger.warning(f"[chat:{action_ctx.chat_id}] event_ref #{event_ref} not found. Falling back to publish.")
        message_id = await _send_reply(action_ctx, valid_points, comment)
        event_num = _generate_event_ref(messages)
        return {
            "messages": [
                ToolMessage(
                    content=f"✅ Event published. event_ref: {event_num} (fallback). Summary: {summary}",
                    tool_call_id=tool_call["id"],
                    additional_kwargs={"message_id": message_id} if message_id else {},
                )
            ]
        }

    old_ai_idx, old_tool_idx = ref_result
    prev_msg_id = None
    if old_tool_idx >= 0:
        prev_msg_id = messages[old_tool_idx].additional_kwargs.get("message_id")

    message_id = await _apply_update_side_effects(
        messages=messages,
        action_ctx=action_ctx,
        valid_points=valid_points,
        comment=comment,
        old_ai_idx=old_ai_idx,
        prev_msg_id=prev_msg_id,
        event_ref=event_ref,
    )

    result_messages: list = []
    old_ai_msg = messages[old_ai_idx]
    if old_ai_msg.id is not None:
        result_messages.append(RemoveMessage(id=old_ai_msg.id))
    if old_tool_idx >= 0 and messages[old_tool_idx].id is not None:
        result_messages.append(RemoveMessage(id=messages[old_tool_idx].id))

    tool_output = f"✅ Event updated. event_ref: {event_ref}. Summary: {summary}"
    if comment:
        tool_output += f". Comment: {comment}"

    result_messages.append(
        ToolMessage(
            content=tool_output,
            tool_call_id=tool_call["id"],
            additional_kwargs={"message_id": message_id} if message_id else {},
        )
    )
    return {"messages": result_messages}


# ── 3. Define Nodes ────────────────────────────────────────────────────────

async def pre_process_node(state: GraphState, config: RunnableConfig) -> dict:
    """
    Optionally returns RemoveMessage commands to keep the state small (e.g. max 15 messages)
    to prevent the SQLite DB from ballooning in size.
    """
    messages = state["messages"]
    
    # Retain system prompts and the most recent 15 messages in DB.
    # We find all messages that are not SystemMessage, and if there's more than 15, we delete the oldest ones.
    history_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
    
    if len(history_msgs) > 15:
        idx = len(history_msgs) - 15
        
        # Walk backwards to ensure the slice starts with a HumanMessage
        # This prevents breaking an AIMessage/ToolMessage sequence.
        while idx > 0 and not isinstance(history_msgs[idx], HumanMessage):
            idx -= 1
            
        if idx > 0:
            to_remove = history_msgs[:idx]
            return {"messages": [RemoveMessage(id=m.id) for m in to_remove if m.id is not None]}

    return {}

async def llm_node(state: GraphState, config: RunnableConfig) -> dict:
    """
    Invokes the LLM with the current list of messages.
    """
    llm_with_tools = get_bound_chat_llm()
    
    # Expose strict Context Limit
    from src.config import get_context_messages_limit
    context_limit = get_context_messages_limit()
    
    # 1. Slice history by literal message count safely
    system_msgs = [m for m in state["messages"] if isinstance(m, SystemMessage)]
    
    # LangGraph best practice: if no system message in state, inject from config.
    # This keeps state raw while ensuring the LLM receives its instructions.
    if not system_msgs:
        sys_prompt = config.get("configurable", {}).get("system_prompt")
        if sys_prompt:
            system_msgs = [SystemMessage(content=sys_prompt)]

    history_msgs = [m for m in state["messages"] if not isinstance(m, SystemMessage)]
    
    if context_limit > 0 and len(history_msgs) > context_limit:
        start_idx = len(history_msgs) - context_limit
        # Walk backwards to ensure the slice starts with a HumanMessage, 
        # avoiding orphaned ToolMessages or raw AIMessages which crash OpenAI.
        while start_idx > 0 and not isinstance(history_msgs[start_idx], HumanMessage):
            start_idx -= 1
        recent_msgs = history_msgs[start_idx:]
    else:
        recent_msgs = history_msgs
        
    context_window = system_msgs + recent_msgs
    
    # 2. Strict Token Trimming Just-In-Time (failsafe)
    from langchain_core.messages import trim_messages
    from src.config import get_max_tokens_limit
    max_tokens = get_max_tokens_limit()
    
    def rough_token_counter(msgs: list) -> int:
        total = 0
        for m in msgs:
            c_len = len(str(m.content)) if m.content else 0
            tc_len = sum(len(str(tc)) for tc in getattr(m, 'tool_calls', []))
            total += (c_len + tc_len) // 4
        return total
        
    trimmed_messages = trim_messages(
        context_window,
        max_tokens=max_tokens,
        strategy="last",
        token_counter=rough_token_counter,
        include_system=True,
        allow_partial=False,
        start_on="human"
    )
    
    response = await llm_with_tools.ainvoke(trimmed_messages)
    return {"messages": [response]}


async def action_node(state: GraphState, config: RunnableConfig) -> dict:
    """
    Executes the chosen tool and handles the side effects.
    """
    thread_id, action_ctx = _get_action_context(config)
    chat_id = config.get("configurable", {}).get("chat_id", "")
    messages = state["messages"]
    last_msg = messages[-1]

    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return {}

    if action_ctx is None:
        logger.error(f"[chat:{chat_id}] Missing action context for thread_id={thread_id}")
        return {"messages": [ToolMessage(content="Error: missing action context.", tool_call_id=last_msg.tool_calls[0]["id"])]}

    tc = last_msg.tool_calls[0]
    tool_name = tc["name"]
    points = tc["args"].get("points", [])
    comment = tc["args"].get("comment", "")

    valid_points = _normalize_points(points)
    if not valid_points:
        logger.warning(f"[chat:{chat_id}] No valid times extracted by LLM (points={points})")
        return _build_validation_error(tc["id"])

    summary = _format_event_summary(valid_points)
    if not action_ctx.sender_registered:
        return _build_registration_gate(tc["id"], tool_name, summary)

    if tool_name == "publish_event":
        return await _execute_publish(messages, tc, action_ctx, valid_points, comment, summary)

    if tool_name == "update_previous_event":
        return await _execute_update(messages, tc, action_ctx, valid_points, comment, summary)

    return {"messages": [ToolMessage(content=f"Error: unsupported tool '{tool_name}'.", tool_call_id=tc["id"])]}


# ── 4. Build Graph ─────────────────────────────────────────────────────────

def should_continue(state: GraphState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "action"
    return END

def action_router(state: GraphState) -> str:
    """Routes back to LLM if the tool produced a validation error, else ends."""
    messages = state["messages"]
    last_message = messages[-1]
    if isinstance(last_message, ToolMessage) and last_message.content.startswith("Error:"):
        return "llm"
    return END

def build_agent_graph() -> StateGraph:
    workflow = StateGraph(GraphState)
    
    workflow.add_node("pre_process", pre_process_node)
    workflow.add_node("llm", llm_node)
    workflow.add_node("action", action_node)

    workflow.add_edge(START, "pre_process")
    workflow.add_edge("pre_process", "llm")
    workflow.add_conditional_edges("llm", should_continue, {"action": "action", END: END})
    workflow.add_conditional_edges("action", action_router, {"llm": "llm", END: END})

    return workflow
