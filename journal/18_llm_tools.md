# Technical Spec: LLM Tools

> **Version**: 1.0 — LangGraph Native Tools

---

## 1. Overview

The event detection agent uses two primary tools to interact with the chat: `publish_event` for initial announcements and `update_previous_event` for refining or overriding previously stated times without flooding the chat.

Both tools share a common schema for extracted data points but differ in their execution logic and historical tracking.

---

## 2. Tool Schemas

### 2.1 Common Data Structure: `Point`

Each "point" extracted by the LLM represents a single time-location event.

| Field | Type | Required | Description |
|---|---|---|---|
| `time` | `string` | Yes | **Strictly `HH:MM`** (24h). No timezones or suffixes. |
| `city` | `string \| null` | Yes | IANA city name or geographical location. |
| `event_type` | `string` | Yes | Short name of the event (e.g., "call", "deadline" "sync"). |

### 2.2 `publish_event`

Called when a new event is detected or a previous event cannot be updated.

**Arguments:**
- `reasoning` (string): Brief internal analysis.
- `points` (List[Point]): One or more event points.

**Logic:**
1. Increments the per-chat event counter (`#N`).
2. Formats a full reply message using `formatter.format_multi_conversion`.
3. Replies to the user's message in the chat.
4. Appends a `ToolMessage` to history: `✅ Published event #N: {summary}`.

### 2.3 `update_previous_event`

Called when a user refines or overrides a time previously handled by the bot.

**Arguments:**
- `reasoning` (string): Explanation of the change.
- `event_ref` (int): The event number to update (from history).
- `points` (List[Point]): The updated points.

**Logic:**
1. Finds the previous bot message for `#event_ref` in the history.
2. Checks the "distance" (number of messages since the original).
3. **If distance ≤ limit**: Edits the original bot message in-place and adds a `🤖` reaction (robot emoji).
4. **If distance > limit**: Deletes the old message and sends a new one (republish).
5. Appends a `ToolMessage` to history: `✅ Published event #N (updated): {summary}`.

---

## 3. Strict Constraints

### 3.1 Time Format
The `time` field **MUST** match the regex `^\d{1,2}:\d{2}$`. Any other format (e.g., "14:00Z", "2pm", "None") will trigger a validation error and force the LLM to retry.

### 3.2 Update Visibility
When calling `update_previous_event`, the LLM is instructed to append `[UPDATED]` to the `event_type` string (e.g., `"созвон [UPDATED]"`) to ensure users notice the change in the edited message.

### 3.3 Zulu Context
While the LLM extracts `HH:MM` for tools, it uses the **Zulu-formatted** `ANCHOR` time and message timestamps in history to resolve relative terms (e.g., "in an hour").

---

## 4. Implementation Reference

- **Schema & Prompt**: `src/event_detection/prompts.py`
- **Orchestration**: `src/event_detection/graph.py` (via `action_node`)
- **Execution**: `src/event_detection/tools.py`
