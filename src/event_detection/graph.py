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
def publish_event(points: list[dict]) -> str:
    """
    Call this tool when the current message contains a NEW time event
    that has not been published yet. Or if there is no previous bot message
    about this event to update.

    Args:
        points: List of event points, each with 'time' (HH:MM), optional 'city',
                and 'event_type' (e.g. 'созвон', 'дедлайн').
    """
    pass

@tool
def update_previous_event(points: list[dict]) -> str:
    """
    Call this tool when the current message OVERRIDES or REFINES a time that
    the bot already published in HISTORY.
    This edits the previous bot message in-place instead of flooding the chat.

    Args:
        points: Updated event points with corrected time/city/event_type.
    """
    pass

tools_list = [publish_event, update_previous_event]


# ── 3. Define Nodes ────────────────────────────────────────────────────────

async def pre_process_node(state: GraphState, config: RunnableConfig) -> dict:
    """
    Optionally returns RemoveMessage commands to keep the state small (e.g. max 15 messages)
    to prevent the SQLite DB from ballooning in size.
    """
    messages = state["messages"]
    
    # Retain system prompts and the most recent 10-15 messages.
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
    
    # Strict Token Trimming Just-In-Time
    from langchain_core.messages import trim_messages
    def rough_token_counter(msgs: list) -> int:
        return sum(len(str(m.content)) // 4 for m in msgs)
        
    trimmed_messages = trim_messages(
        state["messages"],
        max_tokens=2500,
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
        # Should not happen if routing is correct
        return {}
        
    tc = last_msg.tool_calls[0]
    tool_name = tc["name"]
    points = tc["args"].get("points", [])
    
    tool_output_str = "Side-effect executed"
    message_id = None
    
    # ── Execute Side Effects ──
    if build_reply_fn:
        reply = await build_reply_fn(points)
        if reply:
            if tool_name == "publish_event" and send_fn:
                message_id = await send_fn(reply)
                
            elif tool_name == "update_previous_event":
                # The >8 messages logic!
                # 1. Find the last AIMessage generated BEFORE this current run
                # 2. Count HumanMessages after it
                prev_ai_idx = -1
                for i in range(len(messages) - 2, -1, -1):
                    # We look for the last AIMessage that was from the BOT (has a message_id)
                    m = messages[i]
                    if isinstance(m, AIMessage) and m.additional_kwargs.get("message_id"):
                        prev_ai_idx = i
                        break
                        
                if prev_ai_idx != -1:
                    prev_ai_msg = messages[prev_ai_idx]
                    prev_id = prev_ai_msg.additional_kwargs.get("message_id")
                    
                    # Count HumanMessages since then
                    distance = sum(1 for m in messages[prev_ai_idx:] if isinstance(m, HumanMessage))
                    
                    if distance > 8:
                        # Too far up! Delete old, send new.
                        logger.info(f"[chat:{chat_id}] update > 8 messages away ({distance}). Deleting old and republishing.")
                        if delete_fn and prev_id:
                            await delete_fn(prev_id)
                        if send_fn:
                            message_id = await send_fn(reply)
                    else:
                        # Close enough, edit in place
                        logger.info(f"[chat:{chat_id}] update {distance} messages away. Editing in place.")
                        if edit_fn and prev_id:
                            try:
                                await edit_fn(prev_id, reply)
                                message_id = prev_id
                            except Exception as e:
                                logger.warning(f"Edit failed: {e}. Falling back to publish.")
                                if send_fn:
                                    message_id = await send_fn(reply)
                else:
                    # No previous AI message found, fallback to publish
                    if send_fn:
                        message_id = await send_fn(reply)
                        
    # End Side Effects

    # Record the tool output correctly in LangGraph state
    tool_msg = ToolMessage(
        content=tool_output_str,
        tool_call_id=tc["id"],
        # Save our new message_id into the tool message so we can trace it next time!
        # Wait, the best place to save the message_id is usually on the AIMessage, but we can't mutate the AIMessage after creation.
        # We can just put it in the ToolMessage additional_kwargs.
        additional_kwargs={"message_id": message_id} if message_id else {}
    )
    
    return {"messages": [tool_msg]}


# ── 4. Build Graph ─────────────────────────────────────────────────────────

def should_continue(state: GraphState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "action"
    return END

def build_agent_graph() -> StateGraph:
    workflow = StateGraph(GraphState)
    
    workflow.add_node("pre_process", pre_process_node)
    workflow.add_node("llm", llm_node)
    workflow.add_node("action", action_node)

    workflow.add_edge(START, "pre_process")
    workflow.add_edge("pre_process", "llm")
    workflow.add_conditional_edges("llm", should_continue, {"action": "action", END: END})
    workflow.add_edge("action", END)

    return workflow

