# LangSmith Evaluations

Tests the event-detection agent against a curated dataset.

## Prerequisites

`.env` must contain:
```
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=timezone-bot-tests
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

## Workflow

### 1. Upload dataset (one-time, then on cases.yaml changes)
```bash
uv run python tests/langsmith/upload_dataset.py
```
Converts `tests/promptfoo/cases.yaml` → LangSmith Dataset named `timezone-bot-event-detection`.  
Idempotent — safe to re-run.

### 2. Run evaluation
```bash
uv run python tests/langsmith/run_eval.py
```
Runs the real `detect_event()` agent on every case and scores 3 metrics:

| Metric | What it checks |
|---|---|
| `event_detected` | Did the agent say event=true/false correctly? |
| `tool_called` | When event=true, did agent call a tool (not plain JSON)? |
| `time_extracted` | Was at least one HH:MM time extracted? |

Results appear in [LangSmith UI](https://eu.smith.langchain.com) under **timezone-bot-tests**.

## Tracing (automatic)

Every production LangChain call is **already traced** — no code changes needed.  
Just set `LANGSMITH_API_KEY` and run the bot. All agent invocations appear in the UI.

## Bump experiment version

In `run_eval.py`, change `EXPERIMENT_PREFIX`:
```python
EXPERIMENT_PREFIX = "agent-v2"   # after prompt changes
```
This lets you compare runs side-by-side in the LangSmith UI.
