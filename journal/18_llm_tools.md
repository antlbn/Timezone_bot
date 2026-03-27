# Technical Spec: LLM Tools

This document specifies the two tools available to the event-detection agent.

---

## 1. Why tools exist

The agent should not emit free-form “answers” directly as its primary contract.

Instead it must produce one of two explicit intentions:

- create a new event reply,
- update a previously published event reply.

That contract is expressed as tool calls.

---

## 2. Shared Data Structure

Each tool works with a list of `points`.

### 2.1 `Point`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `time` | `string \| null` | Yes | Strict `HH:MM` 24h time. |
| `city` | `string \| null` | Yes | Optional city/location override for source timezone. |
| `event_type` | `string` | Yes | Short event label such as `call`, `sync`, `deadline`. |

### 2.2 Validation rule

Before side effects are executed, points are validated.

Current hard rule:

- `time` must match `^\d{1,2}:\d{2}$`

If no valid times remain after validation:

- nothing is published,
- the tool path returns a corrective ToolMessage instead.

---

## 3. `publish_event`

### 3.1 Intent

Use `publish_event` when the current message introduces a new actionable event for the chat.

### 3.2 Inputs

- `points: list[Point]`
- `comment: str = ""`

### 3.3 Runtime behavior

When `publish_event` is executed:

1. validate `points`;
2. generate a unique 4-digit `event_ref`;
3. build the final formatted reply;
4. call platform `send_fn`;
5. write a ToolMessage into LangGraph state.

Typical ToolMessage content:

```text
✅ Event published. event_ref: 4821. Summary: sync → 14:00, call → 16:30
```

If a user-facing `comment` exists, it is appended to the ToolMessage and to the formatted reply footer.

---

## 4. `update_previous_event`

### 4.1 Intent

Use `update_previous_event` when the current message refines or overrides a previously published event.

### 4.2 Inputs

- `event_ref: int`
- `points: list[Point]`
- `comment: str = ""`

### 4.3 Runtime behavior

When `update_previous_event` is executed:

1. validate `points`;
2. locate the previous ToolMessage by `event_ref`;
3. build the new reply text;
4. decide:
   - edit existing bot message,
   - or delete + republish;
5. remove the old AI+Tool pair from graph state;
6. write a fresh ToolMessage for the updated event.

Typical ToolMessage content:

```text
✅ Event updated. event_ref: 4821. Summary: sync → 15:00
```

If the referenced event cannot be found:

- the action layer falls back to new publication.

Fallback ToolMessage:

```text
✅ Event published. event_ref: 5932 (fallback). Summary: sync → 15:00
```

---

## 5. Edit vs Republish

`update_previous_event` does not always edit in place.

The action layer decides based on:

- whether edit-in-place is enabled,
- how many human messages have passed since the original event.

Rule:

| Condition | Action |
|---|---|
| edit enabled and distance within threshold | edit existing bot message |
| otherwise | delete old message and publish a new one |

This keeps the chat readable when the original reply is already too far above in the conversation.

---

## 6. Relationship to the rest of the system

The tools do **not** perform the actual timezone math themselves.

Their job is to express event intent.

The deterministic layers then do the rest:

1. resolve source timezone,
2. load chat members,
3. convert times,
4. format output,
5. call platform APIs.

---

## 7. Unregistered onboarding behavior

During onboarding-time passes for unregistered users:

- the model may still choose `publish_event` or `update_previous_event`,
- but real chat side effects must not occur,
- and the action layer must write an app-logic skip marker instead of a fake publish/update result.

---

## 8. Rebuild Checklist

To recreate the tool layer faithfully, preserve:

1. Two-tool contract only: `publish_event`, `update_previous_event`.
2. Strict time validation before side effects.
3. Random unique `event_ref` generation.
4. Remove-and-replace semantics for updated events in graph state.
5. Edit-vs-republish policy based on message distance.
