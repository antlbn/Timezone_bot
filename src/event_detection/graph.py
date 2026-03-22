"""
graph.py — LangGraph Definition for Timezone Bot
This module defines the StateGraph, nodes, and tools for the event detection loop.
"""

import os
from typing import Annotated, TypedDict, Any, Callable, Awaitable
from langchain_core.messages import (
    BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage, RemoveMessage
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.logger import get_logger
from src.event_detection.client import get_llm_model
from src.config import get_bot_settings

logger = get_logger()

# ── 1. Define State ────────────────────────────────────────────────────────

class GraphState(TypedDict):
    """
    The state of the conversation graph.
    messages: Built-in LangGraph list of messages with reducer (add_messages).
    """
    messages: Annotated[list[BaseMessage], add_messages]


# ── 2. Define Tools Schema ──────────────────────────────────────────────────

@tool
def publish_event(reasoning: str, points: list[dict]) -> str:
    """
    Call this tool when the current message contains a NEW time event
    that has not been published yet. Or if there is no previous bot message
    about this event to update.

    Args:
        reasoning: Brief explanation: why is this an event? How did you
                   interpret the time? Any geo/timezone notes?
        points: List of event points, each with 'time' (HH:MM), optional 'city',
                and 'event_type' (e.g. 'созвон', 'дедлайн').
    """
    pass

@tool
def update_previous_event(reasoning: str, event_ref: int, points: list[dict]) -> str:
    """
    Call this tool when the current message OVERRIDES or REFINES a time that
    the bot already published in HISTORY.
    This edits the previous bot message in-place instead of flooding the chat.

    Args:
        reasoning: Brief explanation: what changed? How did you re-interpret
                   the time or event?
        event_ref: The event number to update (from "Published event #N" in history).
        points: Updated event points with corrected time/city/event_type.
    """
    pass

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


import re

def _count_published_events(messages: list) -> int:
    """Find the highest event number assigned so far by parsing ToolMessages."""
    max_num = 0
    pattern = re.compile(r"(?:Published|Updated) event #(\d+)")
    for m in messages:
        if isinstance(m, ToolMessage) and m.content:
            match = pattern.search(m.content)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
    return max_num


def _find_event_by_ref(messages: list, event_ref: int) -> tuple[int, int] | None:
    """Find the (ai_idx, tool_idx) pair for a specific event_ref.
    
    Looks for a ToolMessage with 'Published/Updated event #N' and then
    finds its corresponding AIMessage.
    Returns indices into the messages list, or None if not found.
    """
    pattern = re.compile(rf"(?:Published|Updated) event #{event_ref}\b")
    
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
        # Keep the last 15
        to_remove = history_msgs[:-15]
        # Generate RemoveMessage instructions for LangGraph
        return {"messages": [RemoveMessage(id=m.id) for m in to_remove if m.id is not None]}

    return {}

async def llm_node(state: GraphState, config: RunnableConfig) -> dict:
    """
    Invokes the LLM with the current list of messages.
    """
    settings = get_bot_settings()
    temp = settings.get("llm", {}).get("temperature", 0.0)
    model_name = get_llm_model()

    llm = ChatOpenAI(
        model=model_name,
        temperature=temp,
        openai_api_base=os.getenv("LLM_BASE_URL") or None,
        openai_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or "no-key",
    )
    llm_with_tools = llm.bind_tools(tools_list)
    
    # Expose strict Context Limit
    from src.config import get_context_messages_limit
    context_limit = get_context_messages_limit()
    
    # 1. Slice history by literal message count safely
    system_msgs = [m for m in state["messages"] if isinstance(m, SystemMessage)]
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
        return sum(len(str(m.content)) // 4 for m in msgs)
        
    trimmed_messages = trim_messages(
        context_window,
        max_tokens=max_tokens,
        strategy="last",
        token_counter=rough_token_counter,
        include_system=True,
        allow_partial=False
    )
    
    response = await llm_with_tools.ainvoke(trimmed_messages)
    return {"messages": [response]}


async def action_node(state: GraphState, config: RunnableConfig) -> dict:
    """
    Executes the chosen tool and handles the side effects (sending/editing msgs).
    Uses callback functions injected via config.

    Key design:
    - publish_event: sends new message, records "✅ Published event #N: ..."
    - update_previous_event: finds event by event_ref, edits/replaces in chat,
      REMOVES old AI+Tool pair from state so only the updated version remains.
    """
    callbacks = config.get("configurable", {})
    send_fn = callbacks.get("send_fn")
    edit_fn = callbacks.get("edit_fn")
    delete_fn = callbacks.get("delete_fn")
    build_reply_fn = callbacks.get("build_reply_fn")
    chat_id = callbacks.get("chat_id")
    platform = callbacks.get("platform")
    
    messages = state["messages"]
    last_msg = messages[-1]
    
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return {}
        
    tc = last_msg.tool_calls[0]
    tool_name = tc["name"]
    points = tc["args"].get("points", [])
    
    # ── VALIDATION ───────────────────────────────────────────────────────
    import re
    time_pattern = re.compile(r"^\d{1,2}:\d{2}$")
    invalid_points = []
    for p in points:
        t = p.get("time")
        if not isinstance(t, str) or not time_pattern.match(t.strip()):
            invalid_points.append(p)
            
    if invalid_points:
        logger.warning(f"[chat:{chat_id}] Invalid time format from LLM: {invalid_points}")
        err_msg = (
            f"Error: Invalid time format in points {invalid_points}. "
            f"The 'time' field MUST strictly match 'HH:MM' (e.g. '14:00'). "
            f"Do NOT output 'None', do NOT append timezones."
        )
        return {"messages": [ToolMessage(content=err_msg, tool_call_id=tc["id"])]}
        
    summary = _format_event_summary(points)
    
    message_id = None
    result_messages: list = []  # messages to return (ToolMessage + optional RemoveMessages)
    
    # ── PUBLISH ──────────────────────────────────────────────────────────
    if tool_name == "publish_event":
        event_num = _count_published_events(messages) + 1
        
        if build_reply_fn and send_fn:
            reply = await build_reply_fn(points)
            if reply:
                message_id = await send_fn(reply)
        
        tool_output = f"✅ Published event #{event_num}: {summary}"
        result_messages.append(ToolMessage(
            content=tool_output,
            tool_call_id=tc["id"],
            additional_kwargs={"message_id": message_id} if message_id else {},
        ))
    
    # ── UPDATE ───────────────────────────────────────────────────────────
    elif tool_name == "update_previous_event":
        event_ref = tc["args"].get("event_ref", 0)
        ref_result = _find_event_by_ref(messages, event_ref)
        
        if ref_result is None:
            logger.warning(f"[chat:{chat_id}] event_ref #{event_ref} not found. Falling back to publish.")
            # Fallback: treat as new publish
            if build_reply_fn and send_fn:
                reply = await build_reply_fn(points)
                if reply:
                    message_id = await send_fn(reply)
            event_num = _count_published_events(messages) + 1
            tool_output = f"✅ Published event #{event_num} (fallback): {summary}"
            result_messages.append(ToolMessage(
                content=tool_output,
                tool_call_id=tc["id"],
                additional_kwargs={"message_id": message_id} if message_id else {},
            ))
        else:
            old_ai_idx, old_tool_idx = ref_result
            # Get the message_id of the old published message (stored in ToolMessage)
            prev_msg_id = None
            if old_tool_idx >= 0:
                prev_msg_id = messages[old_tool_idx].additional_kwargs.get("message_id")
            
            # Execute side effect: edit or delete+republish in chat
            if build_reply_fn:
                reply = await build_reply_fn(points)
                if reply:
                    # Count HumanMessages since the old event to decide edit vs delete+republish
                    from src.config import get_republish_edited_message_after_distance
                    distance = sum(1 for m in messages[old_ai_idx:] if isinstance(m, HumanMessage))
                    limit = get_republish_edited_message_after_distance()
                    
                    if distance > limit:
                        logger.info(f"[chat:{chat_id}] update event #{event_ref} > {limit} msgs away ({distance}). Delete+republish.")
                        if delete_fn and prev_msg_id:
                            await delete_fn(prev_msg_id)
                        if send_fn:
                            message_id = await send_fn(reply)
                    else:
                        logger.info(f"[chat:{chat_id}] update event #{event_ref} {distance} msgs away. Editing in place.")
                        if edit_fn and prev_msg_id:
                            try:
                                await edit_fn(prev_msg_id, reply)
                                message_id = prev_msg_id
                            except Exception as e:
                                logger.warning(f"Edit failed: {e}. Falling back to publish.")
                                if send_fn:
                                    message_id = await send_fn(reply)
                        elif send_fn:
                            message_id = await send_fn(reply)
            
            # Remove old AI+Tool pair from state so the model sees only the updated version
            old_ai_msg = messages[old_ai_idx]
            if old_ai_msg.id is not None:
                result_messages.append(RemoveMessage(id=old_ai_msg.id))
            if old_tool_idx >= 0 and messages[old_tool_idx].id is not None:
                result_messages.append(RemoveMessage(id=messages[old_tool_idx].id))
            
            # Record the updated event with the SAME event_ref number
            tool_output = f"✅ Published event #{event_ref} (updated): {summary}"
            result_messages.append(ToolMessage(
                content=tool_output,
                tool_call_id=tc["id"],
                additional_kwargs={"message_id": message_id} if message_id else {},
            ))
    
    return {"messages": result_messages}


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

