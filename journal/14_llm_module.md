# Technical Spec: LLM Module

> **Version**: 2.0 — LLM as Orchestrator (Tool-Calling)

---

## 1. Overview

This module describes the full lifecycle of a message from the moment it arrives in the bot
(Telegram or Discord) until the bot sends the converted time back to the chat.

The LLM is now the **orchestrator**, not just a classifier:

1. **Pre-LLM gate** (algorithm): checks that every message author is registered in the DB.
   Unregistered users → onboarding dialog is started; their message is silently dropped from the
   LLM pipeline.
2. **LLM call**: for registered users, the current message + N historical messages from the
   in-memory cache + sender metadata are sent.
   The LLM decides whether the message contains a time-coordination event and fills a structured
   JSON response.
3. **Tool call** (algorithm triggered by LLM): when the LLM identifies an actionable event
   (`event == true`, `times` non-empty), it calls the `convert_time` tool — a thin wrapper
   around the existing Transform module. The module reads participant timezones from DB, converts
   every time value, and posts the formatted result to the chat.

### Why this shape?

| Concern | Old approach | New approach |
|---|---|---|
| Onboarding trigger | Regex detected unknown user | Algorithm checks DB on every message |
| Time detection | Regex prefilter → LLM classify | LLM does both detection and extraction |
| Conversion trigger | Bot code reads LLM JSON, calls Transform | LLM calls `convert_time` tool directly |
| Context window | Two-pass (pass 1 single, pass 2 with history) | Single pass with configurable history |

---

## 2. Key Architectural Principles

- **Single-pass, history-first**: Every LLM call receives the current message together with the
  N most recent messages from the in-memory cache (n controlled by `context_messages` in config).
  The two-pass retry is removed; the bias toward silence (`trigger=false` when uncertain) is
  preserved by the decision policy.
- **LLM is agnostic to platform**: The LLM never sees Telegram/Discord-specific IDs.
  The message window uses an internal normalized representation (section 4.1).
- **In-memory cache only**: History is never persisted. On restart the buffer is empty; the first
  N real messages will refill it.
- **One DB for both platforms**: Telegram and Discord share the same SQLite DB (see `05_storage.md`).
  User lookup uses `platform + platform_user_id` as the composite key.

---

## 3. Module File Map

```
src/
├── llm/
│   ├── __init__.py         # Public API: process_message(platform, chat_id, msg, sender_db)
│   ├── client.py           # OpenAI-SDK client; agnostic base_url config
│   ├── prompts.py          # System prompt + JSON schema + tool definition
│   ├── history.py          # Per-chat deque (ring buffer); snapshot helpers
│   ├── detector.py         # Orchestration: history → LLM → tool dispatch
│   └── tools.py            # convert_time tool wrapper → Transform → Formatter → Reply
```

> **Old module**: `src/event_detection/` is deprecated and will be removed in the next cleanup sprint.

---

## 4. Inputs

### 4.1 Message Window (Context sent to LLM)

Each item in the window (history + current message) is the same normalized shape:

| Field | Type | Notes |
|---|---|---|
| `platform` | `"telegram" \| "discord"` | Source platform |
| `chat_id` | `str` | Normalized string; platform-specific integer cast to str |
| `message_id` | `str` | Platform-specific |
| `author_id` | `str` | Platform user ID (cast to str) |
| `author_name` | `str` | Display name / username |
| `text` | `str` | Truncated to `max_message_length_chars` |
| `timestamp_utc` | `str` | ISO 8601 `Z` suffix, e.g. `2026-03-04T10:00:00Z` |

**Sender fields** (for the newest message only, injected by the gateway before calling the LLM):

| Field | Type | Source |
|---|---|---|
| `sender_id` | `str` | Same as `author_id` of the newest message |
| `sender_name` | `str` | Same as `author_name` of the newest message |
| `sender_timezone_iana` | `str` | From DB (`05_storage.md`) |
| `anchor_timestamp_utc` | `str` | Timestamp of the newest message |

### 4.2 History Buffer

- **Keyed by** `(platform, chat_id)`.
- **Length**: up to `context_messages` items (ring buffer, oldest dropped automatically).
- **Taken before appending** the current message so the snapshot excludes it (see section 6).

---

## 5. Pre-LLM Gate: Registration Check

**Executed by the gateway (adapter), not by the LLM.**

```
Incoming message
        │
        ▼
[DB lookup: sender registered?]
        │
  ┌─────┴──────┐
  NO            YES
  │              │
  ▼              ▼
[Start          [Append to history buffer]
 onboarding         │
 dialog]            ▼
                [LLM pipeline ──▶ section 6]
```

### Rules

1. **Not registered**: trigger the onboarding flow (`08_telegram_commands.md` / Discord equivalent).
   The original message is **appended to the history buffer** (for future context) but is **not**
   sent to the LLM.
2. **Registered**: proceed to LLM.
3. **Onboarding timeout / incomplete**: the user stays unregistered; subsequent messages from them
   repeat rule 1 — they are never sent to the LLM until `sender_timezone_iana` is stored in DB.

> **Rationale**: We never wait — other participants' messages flow through normally while the
> unregistered user completes onboarding. Silence is the correct behavior for unknown senders.

---

## 6. LLM Pipeline

### 6.1 Snapshot (frozen history)

```python
async def process_message(platform, chat_id, msg):
    key = (platform, chat_id)
    dq = message_history.setdefault(key, deque(maxlen=context_messages))

    # 1. Freeze history BEFORE appending current message
    snapshot = list(dq)      # [msg_n-3, msg_n-2, msg_n-1] — up to context_messages items

    # 2. Append current message (for future callers)
    dq.append(msg)

    # 3. Per-chat lock: one LLM call at a time
    lock = chat_locks.setdefault(key, asyncio.Lock())
    if lock.locked():
        return   # msg is in deque; will be used as history for next call

    async with lock:
        await run_llm(msg, snapshot, sender_db)
```

### 6.2 Prompt Composition

The system prompt remains in `prompts.py`. The user-turn message sent to the LLM is a plain-text
block with clearly labelled sections:

```
SENDER: id=123456  name=Alice
ANCHOR: 2026-03-13T17:00:00Z

HISTORY:
[Bob]: We should sync soon.
[Carol]: Agreed, let's pick a time.

CURRENT MESSAGE:
[Alice]: Созвон завтра в 14:00?
```

> Why plain text? Most models (including small ones used via Ollama) are more reliable with
> structured plain text than with JSON-in-JSON user turns.

### 6.3 LLM JSON Response Schema

The LLM **MUST** output strict JSON only (no prose). Schema stored at
`journal/14_llm_module.schema.json`.

```json
{
  "reflections": {
    "event_logic": "Alice proposes a call tomorrow at 14:00",
    "time_logic": "14:00 is explicit, no AM/PM ambiguity",
    "geo_logic": "no location mentioned"
  },
  "event": true,
  "sender_id": "123456",
  "sender_name": "Alice",
  "time": ["14:00"],
  "city": [null]
}
```

> **Chain-of-thought via `reflections`**: the model fills `reflections` before `event`/`time`/`city`
> to improve accuracy on ambiguous cases. Fields are validated but not shown to users.

> **`time` and `city` are parallel arrays of the same length.** `city[i]` is the explicit timezone
> context for `time[i]`. Use `null` when no city was mentioned for that time entry.

**Field reference:**

| Field | Type | Description |
|---|---|---|
| `reflections` | `object` | Chain-of-thought: `event_logic`, `time_logic`, `geo_logic` (all strings) |
| `event` | `bool` | `true` → actionable time event; LLM calls `convert_time` tool |
| `sender_id` | `str` | Echoed from `SENDER: id=…`; passed directly to tool call |
| `sender_name` | `str` | Echoed from `SENDER: name=…`; used in formatted reply |
| `time` | `str[]` | Extracted times in 24h format, e.g. `["14:00", "09:30"]`. Empty `[]` when `event=false` |
| `city` | `(str\|null)[]` | Parallel to `time`. City/region as explicit TZ context, or `null` → sender DB TZ |

### 6.4 Decision Policy

**Set `event=true`, `polarity="positive"` when:**
- Proposed joint meetings / calls / events: «завтра в 14:00 созвон», «встретимся в 19:00»
- Time windows of availability offered to others: «я смогу в 10 и в 14:00, выбирайте»

**Set `event=false`, `polarity="negative"`, `times=[]`, `event_location=null` when:**
- Past references: «я вчера в 8 уже спал»
- Refusal / unavailability: «I cannot be on the meeting at 15:30»
- Personal plans irrelevant to others: «я завтра пойду погуляю с собакой»
- Open question, no decision: «как думаете во сколько нужно созвониться?»
- No time mention at all

> **Bias toward silence**: when uncertain, prefer `event=false`. The bot should be quiet more
> often than it fires.

---

## 7. Tool Call: `convert_time`

### 7.1 When the LLM triggers it

The LLM calls `convert_time` when **both** conditions are met:
- `event == true`
- `times` is non-empty

The tool is defined in the system prompt as an OpenAI-compatible function tool.

### 7.2 Tool Input

```json
{
  "sender_id": "123456",
  "sender_name": "Alice",
  "time": ["14:00", "15:30"],
  "city": ["New York", null]
}
```

| Field | Required | Description |
|---|---|---|
| `sender_id` | yes | Platform user ID (string) |
| `sender_name` | yes | Display name for formatting |
| `time` | yes | Non-empty list of time strings from LLM |
| `city` | yes | Parallel array to `time`. Each entry: city name or `null` (→ sender DB TZ) |

### 7.3 Tool Execution (Algorithm)

The tool iterates over `(time[i], city[i])` pairs:

```
For each (time_str, city) in zip(time, city):
        │
        ▼
  [Resolve source TZ for this entry]
        │
   city non-null?
        │
  ┌─────┴────────────┐
  YES                NO
  │                  │
  ▼                  ▼
geocode(city)        sender DB timezone
→ IANA TZ           (from 05_storage.md via sender_id)
        │
        └──────────────────┐
                           ▼
              [Transform Module — 03_transformation_specs.md]
              source_tz → UTC → each participant's local TZ
              Participants list = all members of (platform, chat_id) from DB
              Sender's own TZ is always included
                           │
                           ▼
              [Formatter — 07_response_format.md]
              Build human-readable message
                           │
                           ▼
              [Reply to chat (one reply per time entry)]
```

**Geocoding fallback**: if city geocoding fails (unknown city, typo) → fall back to sender's DB TZ
and log a warning. Mirrors behavior in `03_transformation_specs.md`.

### 7.4 Output Message Format

When `city[i]` is **null** (sender TZ used as source):

```
📅 Alice: 14:00
─────────────────
🇩🇪 Alice (Berlin)    14:00
🇺🇸 Bob (New York)    08:00
🇯🇵 Carol (Tokyo)     21:00
```

When `city[i]` is **non-null** (e.g. `"New York"`):

```
📅 Alice: 14:00 по Нью-Йорку
─────────────────
🇺🇸 New York (origin)  14:00
🇩🇪 Alice (Berlin)     20:00
🇺🇸 Bob (New York)     14:00
🇯🇵 Carol (Tokyo)      03:00⁺¹
```

> Exact formatting template is owned by `07_response_format.md`. This section defines the
> **data contract** → what fields the tool passes to the Formatter.

---

## 8. Configuration (`configuration.yaml`)

llm:
  enabled: true

  # Number of previous messages included in every LLM call (in-memory cache).
  # These are NOT persisted — lost on restart.
  context_messages: 5

  # Safety cap: messages longer than this are truncated before storing in the deque.
  max_message_length_chars: 500
```

**LLM provider** — configured via `.env` (never in YAML):

```ini
LLM_BASE_URL=https://api.openai.com/v1   # or http://localhost:11434/v1 for Ollama
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...                       # any non-empty string for Ollama
```

---

## 9. Integration Points

| Platform | Adapter file | Notes |
|---|---|---|
| Telegram | `src/commands/common.py` | Runs in own OS thread with own asyncio loop |
| Discord | `src/discord/events.py` | Same pattern |

Both adapters share:
- `message_history` dict (keyed by `(platform, chat_id)`)
- `chat_locks` dict
- Storage (SQLite) via `05_storage.md`

LLM HTTP calls are stateless and safe to run concurrently across both threads.

### Full Message Flow

```
Adapter (TG/Discord)
        │
        ▼
[DB: sender registered?]
   NO ──▶ [Onboarding dialog] → append to history → STOP
   YES
        │
        ▼
[Append to history deque (after snapshot)]
        │
        ▼
[LLM: system prompt + history snapshot + current message + sender metadata]
        │
        ▼
[LLM JSON response]
        │
   event=true AND times non-empty?
        │
   ┌────┴──────┐
   NO          YES
   │            │
 STOP          [LLM calls convert_time tool]
                │
                ▼
         [Resolve source TZ]
         (geocode event_location OR sender DB TZ)
                │
                ▼
         [Transform → all participants]
                │
                ▼
         [Formatter → chat reply]
```

---

## 11. Evaluation Strategy (Promptfoo)

Testing strategy is unchanged from the previous MVP layer:
- `tests/promptfoo/promptfooconfig.yaml`
- `tests/promptfoo/cases.yaml`

Each test case must assert: `event`, `polarity`, `times[]`, `event_location`, and optionally
`sender_id` / `sender_name` echo.

---

## 12. Non-Goals (v2.0)

- Recurring meetings («каждый вторник»)
- Full participant extraction from message text
- Fallback to regex time extraction if LLM is unavailable
- Updating sender's DB timezone from `event_location`
- Persisting history buffer across restarts
