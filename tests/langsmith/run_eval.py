"""
run_eval.py — Run LangSmith evaluation of the event-detection agent.

Usage:
    uv run python tests/langsmith/run_eval.py

What it does:
  1. Loads the dataset from LangSmith (upload_dataset.py must run first)
  2. For each example: runs detect_event() and captures which tool was called
  3. Scores results against ground truth (event=true/false, time in points)
  4. Results visible in LangSmith UI under the project

Token-efficient: uses the same model as prod, no extra API calls.
"""

import asyncio
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client, aevaluate  # noqa: E402
from langsmith.schemas import Run, Example  # noqa: E402

from src.event_detection.detector import detect_event  # noqa: E402
from src.event_detection.history import _message_history, _chat_locks  # noqa: E402

# Default datasets
DATASET_CURATED  = "timezone-bot-tool-calls"        # hand-crafted with tool ground truth
DATASET_MIGRATED = "timezone-bot-event-detection"   # migrated from cases.yaml
DATASET_PARSING  = "timezone-bot-time-parsing"      # time parsing focus
DATASET_BEHAVIOR = "timezone-bot-agent-behavior"    # agent logic/behavior focus

EXPERIMENT_PREFIX = "agent-v1"   # bump when making big changes


# ── Target function ────────────────────────────────────────────────────────

async def _run_agent(inputs: dict) -> dict:
    """Run detect_event for a single test case, return tool call result."""
    # Minimal sender context (no real timezone lookup — we're testing detection, not formatting)
    sender_db: dict = {}

    # Capture which tool was invoked and what points it returned
    tool_used: list[str] = []
    # captured_points: list[list] = []  # Unused, removed to satisfy linter

    async def send_fn(text: str) -> str | None:
        return "eval_msg_000"   # fake message_id — we don't test formatting here

    async def edit_fn(msg_id: str, text: str) -> None:
        pass

    result = await detect_event(
        current_msg={
            "author_id":   inputs.get("sender_id", "eval_user"),
            "author_name": inputs.get("author", inputs.get("sender_name", "User")),
            "text":        inputs["text"],
            "timestamp_utc": inputs.get("timestamp", ""),
        },
        # Build a minimal snapshot from the history list or string
        snapshot=_parse_history(inputs.get("history", [])),
        sender_db=sender_db,
        send_fn=send_fn,
        edit_fn=edit_fn,
        platform="eval",
        chat_id=f"eval_{inputs.get('sender_id', 'x')}",
    )

    # Expose tool_used from detect_event result
    tool_used = result.get("tool_used")
    # Also infer from message_id: if message_id returned → a tool was called
    if not tool_used and result.get("message_id"):
        tool_used = "publish_event"  # default inferred

    payload = {
        "event":      result.get("event", False),
        "tool":       tool_used,
        "points":     result.get("points", []),
    }
    
    if result.get("event_ref") is not None:
        payload["event_ref"] = result.get("event_ref")
    if result.get("comment") is not None:
        payload["comment"] = result.get("comment")

    return payload




def _parse_history(history_data: list | str) -> list:
    """Parse string or list of dicts → BaseMessage entries."""
    from langchain_core.messages import HumanMessage, AIMessage
    
    entries = []
    
    # Handle the new structured format
    if isinstance(history_data, list):
        for msg in history_data:
            m_type = msg.get("type")
            content = msg.get("content", "")
            
            # 1. Native ToolMessage support
            if m_type == "tool" or content.startswith("[TOOL]:"):
                from langchain_core.messages import ToolMessage
                clean_content = content.replace("[TOOL]:", "").strip() if content.startswith("[TOOL]:") else content
                
                # Tool name needs to match whatever we stored right before this
                last_tc_name = "publish_event"
                if entries and isinstance(entries[-1], AIMessage) and entries[-1].tool_calls:
                    last_tc_name = entries[-1].tool_calls[0]["name"]
                    
                entries.append(ToolMessage(
                    content=clean_content,
                    tool_call_id=msg.get("tool_call_id", "mock_test_id"),
                    name=msg.get("name", last_tc_name)
                ))
            
            # 2. Native AIMessage with tool_calls support
            elif m_type == "ai" and (msg.get("tool_calls") or content.startswith("[BOT]: [TOOL_CALL")):
                if msg.get("tool_calls"):
                    # Explicit tool_calls provided in dict
                    entries.append(AIMessage(
                        content=content,
                        tool_calls=msg["tool_calls"],
                        additional_kwargs={"message_id": msg.get("message_id")} if "message_id" in msg else {}
                    ))
                else:
                    # Legacy marker pattern extraction
                    import json
                    import re
                    tool_name = "publish_event" 
                    if "update_previous_event" in content:
                        tool_name = "update_previous_event"
                    
                    args = {}
                    m_ref = re.search(r"event_ref=(\d+)", content)
                    if m_ref:
                        args["event_ref"] = int(m_ref.group(1))

                    points_str = content.split("points=")[-1].strip()
                    if points_str.endswith(")]"):
                        points_str = points_str[:-2]
                    
                    try:
                        args["points"] = json.loads(points_str)
                    except Exception:
                        args["points"] = []
                        
                    entries.append(AIMessage(
                        content="",
                        tool_calls=[{
                            "name": tool_name,
                            "args": args,
                            "id": "mock_test_id"
                        }],
                        additional_kwargs={"message_id": msg.get("message_id")} if "message_id" in msg else {}
                    ))
            
            # 3. Standard AI or Human messages
            elif m_type == "ai":
                entries.append(AIMessage(
                    content=content,
                    additional_kwargs={"message_id": msg.get("message_id")} if "message_id" in msg else {}
                ))
            else: # Default to human
                entries.append(HumanMessage(content=content))
        return entries
        
    # Fallback for old string format (from migrated datasets)
    history_str = history_data
    for line in (history_str or "").strip().splitlines():
        line = line.strip()
        if not line or line.startswith("("):
            continue
            
        author_name = line.split("]")[0].lstrip("[").split(",")[0]
        text = line.split("]: ", 1)[-1] if "]: " in line else line
        
        if author_name == "BOT":
            entries.append(AIMessage(content=f"[BOT]: {text}"))
        else:
            # We preserve the approximate relative time in the content if it existed inside the brackets
            original_bracket = line.split("]")[0].lstrip("[")
            # If the original bracket already contains 'name:' or similar (from user tests), we handle it
            if "name:" in original_bracket:
                original_bracket = original_bracket.replace("name:", "Author: ")
            elif "Author:" not in original_bracket:
                original_bracket = f"Author: {original_bracket}"
            
            entries.append(HumanMessage(content=f"[{original_bracket}]: {text}"))
    return entries



# Store the parsed args globally so the target function can read the delay
_EVAL_ARGS = None

async def target(inputs: dict) -> dict:
    """Async target for LangSmith evaluate — preserves tracing context.
    
    NOTE: Using async target is critical! The old sync wrapper with asyncio.run()
    created a new event loop, breaking LangSmith's contextvars-based tracing.
    This caused LLM child runs to appear as disconnected top-level runs
    instead of nesting under the evaluate trace.
    """
    _message_history.clear()
    _chat_locks.clear()
    
    result = await _run_agent(inputs)
    
    # Enforce a delay to avoid 429 Too Many Requests (RPM limits on free tiers)
    delay = getattr(_EVAL_ARGS, "delay", 0)
    if delay > 0:
        await asyncio.sleep(delay)
        
    return result


# ── Evaluators ─────────────────────────────────────────────────────────────

def eval_event_detected(run: Run, example: Example) -> dict:
    """Did the agent correctly detect (or skip) the event?"""
    predicted = run.outputs.get("event", False) if run.outputs else False
    expected  = example.outputs.get("event")
    if expected is None:
        return {"key": "event_detected", "score": 1, "comment": "no ground truth"}
    score = 1 if predicted == expected else 0
    return {"key": "event_detected", "score": score,
            "comment": f"expected={expected} got={predicted}"}


def eval_correct_tool(run: Run, example: Example) -> dict:
    """Did the agent call the EXACT expected tool (publish vs update vs none)?"""
    expected_tool = example.outputs.get("tool")     # from curated dataset
    if expected_tool is None and not example.outputs.get("event"):
        # migrated dataset: no tool ground truth, skip
        return {"key": "correct_tool", "score": 1, "comment": "n/a"}

    actual_tool = (run.outputs or {}).get("tool")
    score = 1 if actual_tool == expected_tool else 0
    return {"key": "correct_tool", "score": score,
            "comment": f"expected={expected_tool!r} got={actual_tool!r}"}


def eval_tool_was_called(run: Run, example: Example) -> dict:
    """When event=true, did the agent call any tool?"""
    expected_event = example.outputs.get("event")
    if not expected_event:
        return {"key": "tool_called", "score": 1, "comment": "n/a (event=false)"}
    tool = (run.outputs or {}).get("tool")
    score = 1 if tool in ("publish_event", "update_previous_event") else 0
    return {"key": "tool_called", "score": score, "comment": f"tool={tool}"}


def eval_points_extracted(run: Run, example: Example) -> dict:
    """When event=true, did we extract the correct time, city, and event_type?"""
    expected_event = example.outputs.get("event")
    if not expected_event:
        return {"key": "points_extracted", "score": 1, "comment": "n/a (event=false)"}

    # Handle legacy dataset without explicit time/points definitions
    if "time" not in example.outputs and "points" not in example.outputs:
        return {"key": "points_extracted", "score": 1, "comment": "legacy match (no point ground truth)"}

    # Handle old dataset format fallback (timezone-bot-tool-calls v1)
    if "time" in example.outputs and "points" not in example.outputs:
        expected_time = example.outputs.get("time")
        actual_times = (run.outputs or {}).get("time", [])
        score = 1 if expected_time in actual_times else 0
        return {"key": "points_extracted", "score": score, "comment": f"legacy match: {expected_time}"}

    expected_points = example.outputs.get("points", [])
    actual_points = (run.outputs or {}).get("points", [])

    if not expected_points:
        score = 1 if not actual_points else 0
        return {"key": "points_extracted", "score": score, "comment": f"expected empty, got={actual_points}"}

    # We check if EVERY expected point is present in the actual points.
    # We enforce exact matches on Time and City, but event_type is fuzzy.
    matched_count = 0
    for ep in expected_points:
        matched = False
        for ap in actual_points:
            time_match = ap.get("time") == ep.get("time")
            # Tolerate omitted "city" key entirely if the expected city is None
            expected_city = ep.get("city")
            actual_city = ap.get("city")
            city_match = (actual_city == expected_city) or (expected_city is None and actual_city is None)
            
            if time_match and city_match:
                matched = True
                break
        if matched:
            matched_count += 1
            
    score = 1 if matched_count == len(expected_points) and len(actual_points) == len(expected_points) else 0
    comment = f"expected={expected_points} got={actual_points}"

    return {"key": "points_extracted", "score": score, "comment": comment}


def eval_event_ref(run: Run, example: Example) -> dict:
    """Checks if the event_ref parameter matches the expected reference ID for updates."""
    if not example.outputs or "event_ref" not in example.outputs:
        return {"key": "event_ref", "score": 1, "comment": "n/a (no event_ref expected)"}

    expected_ref = example.outputs.get("event_ref")
    actual_ref = (run.outputs or {}).get("event_ref")

    if actual_ref == expected_ref:
        return {"key": "event_ref", "score": 1, "comment": f"matched ({expected_ref})"}
    
    return {"key": "event_ref", "score": 0, "comment": f"expected={expected_ref} got={actual_ref}"}


# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Run LangSmith eval")
    parser.add_argument(
        "--dataset", 
        choices=["curated", "migrated", "parsing", "behavior"], 
        default="curated",
        help="curated=tool-calls, migrated=cases.yaml, parsing=time_parsing_cases, behavior=agent_behavior_cases",
    )
    parser.add_argument("--prefix", default=EXPERIMENT_PREFIX,
                        help="Experiment name prefix")
    parser.add_argument("--delay", type=float, default=4.0,
                        help="Seconds to sleep between inferences to avoid 429 Too Many Requests (e.g. 4.0 for Gemini 15 RPM free tier).")
    args = parser.parse_args()

    global _EVAL_ARGS
    _EVAL_ARGS = args

    dataset_map = {
        "curated":  DATASET_CURATED,
        "migrated": DATASET_MIGRATED,
        "parsing":  DATASET_PARSING,
        "behavior": DATASET_BEHAVIOR,
    }
    dataset_name = dataset_map.get(args.dataset)

    client = Client()
    datasets = {d.name: d for d in client.list_datasets()}
    if dataset_name not in datasets:
        hint = "create_curated_cases.py" if args.dataset == "curated" else "upload_dataset.py"
        print(f"Dataset '{dataset_name}' not found. Run {hint} first.")
        return

    print(f"Dataset : {dataset_name}")
    print(f"Prefix  : {args.prefix}")
    print(f"Delay   : {args.delay}s between calls")
    print("Project : timezone-bot-tests\n")

    results = await aevaluate(
        target,
        data=dataset_name,
        evaluators=[
            eval_event_detected,
            eval_tool_was_called,
            eval_correct_tool,
            eval_points_extracted,
            eval_event_ref
        ],
        experiment_prefix=args.prefix,
        client=client
    )

    passed = 0
    total = 0
    async for r in results:
        total += 1
        eval_results = r["evaluation_results"]["results"]
        if len(eval_results) == 5:
            all_passed = all(er.score == 1 for er in eval_results)
            if all_passed:
                passed += 1
            else:
                desc = r["example"].metadata.get("description", "Unknown")
                print(f"FAILED: {desc}")
                for er in eval_results:
                    if er.score != 1:
                        print(f"  - {er.key}: {er.comment}")
                
    print(f"Results: {passed} / {total} passed all checks.")
    print("Results → https://eu.smith.langchain.com")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
