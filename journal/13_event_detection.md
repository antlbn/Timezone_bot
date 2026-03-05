# Technical Spec: Event Detection (LLM Layer)

## 1. Overview (MVP v1)

This module decides whether a chat message contains a **practically useful time mention** (for coordination / availability / meeting) and — if yes — **extracts the relevant times and optional event location** directly.

LLM produces a **strict JSON** payload that acts as a **binary trigger + extraction result**:
- Should the bot **react** (run conversion)?
- Or should it **ignore** this message window?
- If reacting: what **times** were mentioned, and in which **location** context?

### Key architectural points
- **LLM is the primary layer**: Every message goes to the LLM by default.
- **Optional Prefilter**: Before reaching the LLM, an optional regex/keyword prefilter can be enabled to save costs. By default, it is **off** and every message is sent directly to the LLM.
- **LLM is Agnostic**: The LLM simply receives the message window, evaluates it, and fills the JSON.
- **Time Extraction**: The **actual time extraction** (`times[]`) is performed entirely by the LLM. The optional prefilter only gates whether to call the LLM at all — it never extracts times.

---

## 2. Inputs

### 2.1 Message Window (Context)
The detector receives a configurable window of the last **N** messages for the same chat/guild.

Each message item must include:
- `platform`: `telegram|discord`
- `chat_id`: string or integer (platform-specific)
- `message_id`: string (platform-specific)
- `author_id`: string or integer
- `author_name`: string
- `text`: string
- `timestamp_utc`: ISO 8601 Z (e.g. `2026-03-04T10:00:00Z`)

### 2.2 Sender Context (DB)
From storage (`05_storage.md`), for the sender of the **newest** message in the window.

- `sender_timezone_iana`: IANA name (e.g. `Europe/Berlin`) — used as conversion source if `event_location` is null.
- Optional: `sender_city`, `sender_flag` (for debugging / future UX)

> **New User case**: If the sender is not yet in DB, this field is `null`. See Section 7 for handling.

### 2.3 Anchor Time
- `anchor_timestamp_utc`: timestamp of the newest message in the window

Used to resolve relative expressions: "завтра", "через 2 часа".
> **Note on +1/-1 days**: The LLM extracts the target *time* (e.g. "08:00"). Downstream, the `Transform` module handles relative date shifts (+1/-1 days) locally for each participant based on their timezone. The LLM does not need to compute absolute dates for each timezone.

---

## 3. Output Contract (MVP v1)

### 3.1 Top-level shape (strict JSON)
LLM MUST output JSON only (no prose), matching:

```json
{
  "trigger": true,
  "polarity": "positive",
  "confidence": 0.92,
  "reason": "Meeting anchored to New York time",
  "times": ["14:00", "15:30"],
  "event_location": "New York"
}
```

Fields:
- `trigger: bool`
  - `true` → bot **should** react (run conversion).
  - `false` → bot **should ignore** this message window.
- `polarity: "positive" | "negative"`
  - `positive` → time mention is useful for coordination / availability / joint work.
  - `negative` → time mention is past, refusal, purely personal, or otherwise irrelevant.
- `confidence: float [0,1]`
  - Model's self-estimated confidence in this decision.
- `reason: string`
  - Short free-text explanation (RU/EN) for logs and debugging.
- `times: string[]`
  - List of time strings extracted from the message window (e.g. `["14:00", "завтра в 9"]`).
  - **Empty array `[]` when `trigger=false`.**
  - LLM extracts these; downstream transform layer parses them.
- `event_location: string | null`
  - City or location name **explicitly mentioned in the message** as the timezone context for the event.
  - Example: `"New York"` from «давайте в 12:00 по ньюйорку».
  - `null` if no explicit location is mentioned → sender's DB timezone is used as source.
  - **Scope**: applies only to this conversion; does NOT update the DB.

### 3.2 Source Timezone Resolution

After receiving the LLM output, the app resolves the **source timezone** for conversion using this priority:

```
1. event_location (explicit in messages)
   └─▶ geocode(event_location) → IANA TZ → use as source pivot

2. sender's DB timezone (fallback)
   └─▶ sender_timezone_iana from storage → use as source pivot
```

- If the user **explicitly mentioned a location** (e.g. "по Берлину", "New York time") → `event_location` is non-null → geocode it → use that IANA TZ as source.
- If **no location was mentioned** → `event_location` is `null` → use the sender's stored DB timezone.
- **Fallback**: if geocoding of `event_location` fails (unknown city, typo) → fall back to sender's DB timezone and log a warning.

This logic is also described in `03_transformation_specs.md`.

### 3.3 event_location Geocoding
When `event_location` is non-null:
1. App calls geocoding (`geo.py`, same as `06_city_to_timezone.md`) to resolve city → IANA TZ.
2. That IANA TZ is used as the **source pivot** for conversion (instead of sender's DB TZ).
3. All chat members — **including the sender** — receive their local equivalent of the event time.
4. **Fallback**: if geocoding fails → fall back to sender's DB timezone and log a warning.

### 3.4 JSON Schema file
Formal JSON Schema is stored at: `journal/13_event_detection.schema.json`.

---

## 4. Decision Policy (MVP v1)

### 4.1 When to set `trigger = true` (positive)

Set `trigger=true`, `polarity="positive"` when the time mention is **practically useful** for others in the chat:

- Joint meetings / calls / events:
  - «завтра в 14:00 созвон»
  - «встретимся в 19:00»
  - «Ivan wants to meet tomorrow at 15:30 for all crew»
- Time windows of **availability for others**:
  - «если я завтра буду с заказчиком в 8:00, смогу у него спросить»
  - «я смогу в 10 и в 14:00, выбирайте»

LLM extracts the matching `times[]` and sets `event_location` if a timezone context is mentioned.

### 4.2 When to set `trigger = false` (negative)

Set `trigger=false`, `polarity="negative"`, `times=[]`, `event_location=null` when:

- **Past references**:
  - «я вчера в 8 уже спал»
- **Отказ / недоступность**:
  - «I cannot be on the meeting at 15:30»
  - «завтра в 8 и в 18 буду на спорте»
- **Личные планы, не влияющие на других**:
  - «я завтра пойду погуляю с собакой»
- **Вопросы без решения**:
  - «как думаете во сколько нужно созвониться?»
  - «в 8:00 по Лондону?» (если нет явного решения в окне)
- **No time mention at all**

В спорных случаях модель должна **предпочитать `trigger=false`** — бот должен молчать чаще, чем шуметь.

---

## 5. Optional Prefilter Logic (Cost Saving)

To avoid sending every single chat message to the LLM, you can optionally enable the prefilter (`src/capture.py`).

1. **Strict time regex** (from `02_capture_logic.md`).
2. **Numeric candidate regex** (plain hours like «8» or «19») + **Keywords** (like «созвон», «call»).

### Prefilter Decision (if `prefilter.enabled == true`)
LLM is called ONLY if:
- **any strict time match** is found, OR
- **any numeric candidate match** is found AND there is at least one relevant keyword in the recent messages.

If the prefilter is **disabled** (default), this step is entirely skipped and every message goes to the LLM.

> **Default behaviour**: prefilter is OFF. Every message reaches the LLM. Enable only if LLM cost becomes a concern in high-traffic chats.

---

## 6. Confidence & Extended Context

LLM is called in **at most two passes**. The retry exists solely to resolve ambiguity — it is not a default step.

### Decision tree

```
Pass 1: LLM receives current message only
            │
     confidence >= threshold?
            │
    ┌───────┴────────┐
   YES               NO  (uncertain)
    │                 │
 trigger=true?        │
    │            Pass 2: LLM receives current message
 ┌──┴──┐               + N previous messages (extended_context_messages)
 YES   NO                    │
 │     │             confidence >= threshold?
 ACT  IGNORE                 │
               ┌─────────────┴─────────────┐
              YES                           NO
               │                            │
        trigger=true?                    IGNORE  (silence is safer)
          ┌───┴───┐
         YES      NO
          │        │
         ACT    IGNORE
```

### Rules
- **Pass 1**: LLM receives only the single incoming message (no history).
- **Pass 2**: triggered only if `confidence < min_confidence_trigger` after Pass 1.
  LLM receives the current message **plus** the `snapshot` — the N messages that preceded it (see 6.1).
  The snapshot is fixed at message-arrival time; the live deque is **not** used for Pass 2.
- **After Pass 2**: if still uncertain OR `trigger=false` → do nothing. No third pass.
- **Bias towards silence**: when in doubt at any stage, the bot does nothing.

### 6.1 Message History Buffer

Recent messages for Pass 2 are kept in an **in-memory per-chat ring buffer** (`collections.deque`).

```python
from collections import deque
import asyncio

# Keyed by (platform, chat_id).
message_history: dict[tuple[str, str], deque] = {}
chat_locks:      dict[tuple[str, str], asyncio.Lock] = {}
```

Each entry in the deque is a dict matching the message window schema (section 2.1).

### 6.2 Snapshot — context frozen at arrival time

The snapshot is taken **before** appending the current message to the deque.
It captures the N messages that immediately preceded the current one.

```python
async def handle_message(platform, chat_id, msg):
    key = (platform, chat_id)
    dq = message_history.setdefault(key, deque(maxlen=extended_context_messages))

    # 1. Freeze context BEFORE mutating the deque
    snapshot = list(dq)          # ← [msg_n-3, msg_n-2, msg_n-1]  (up to N items)

    # 2. Now add current message
    dq.append(msg)

    # 3. Acquire per-chat lock — only one LLM pipeline per chat at a time
    lock = chat_locks.setdefault(key, asyncio.Lock())
    if lock.locked():
        return  # chat already being processed; msg is in deque for future context

    async with lock:
        await run_llm_pipeline(msg, snapshot)
```

**Why snapshot instead of live deque for Pass 2:**
- The chat may receive new messages while the LLM is processing (e.g. `"Ок"`, `"видели новый инструмент?"`)
- The live deque shifts — old relevant messages get pushed out, new unrelated ones come in
- The snapshot is immutable: Pass 2 always sees the same preceding context as was present when the message arrived

**Behaviour summary:**
- `snapshot` = messages that existed **before** the current one arrived (max `extended_context_messages` items)
- New messages that arrive while the lock is held are added to the deque but do **not** trigger a new LLM call
- On bot restart the buffer is empty — Pass 2 will have an empty snapshot; bot stays silent if uncertain (acceptable)
- The buffer is **never persisted to disk**. No SQL, no files.

---

## 7. Configuration (`configuration.yaml`)

```yaml
event_detection:
  enabled: true
  min_confidence_trigger: 0.75

  # Pass 1: LLM sees only the current message (no history).
  # Pass 2 (retry on low confidence): adds this many previous messages.
  extended_context_messages: 3

  # Protection against token limit exhaustion.
  # Messages longer than this are truncated before adding to deque/LLM.
  max_message_length_chars: 500

  prefilter:
    enabled: false  # Default OFF = LLM processes every message
    require_time_regex_or_keywords: true
    # ... keywords list defined in capture section ...
```

Notes:
- `prefilter.enabled == false` (default) → all messages reach the LLM.
- `prefilter.enabled == true` → messages not passing regex/keyword gate are dropped silently.

**LLM provider** — set via `.env` (never in YAML):
```ini
LLM_BASE_URL=https://api.openai.com/v1   # or http://localhost:11434/v1 for Ollama
LLM_MODEL=gpt-4o-mini                    # or llama3.2, etc.
LLM_API_KEY=sk-...                       # any string for Ollama
```
Switching providers = changing `.env` only. No code changes.

---

## 8. New User Flow Integration

When any message is received from a sender **not found in DB**:

1. **Immediate Onboarding**: activate the onboarding flow immediately (Bot asks the user for their city → geocode → save to DB).
2. **LLM Evaluation**: the original message is **not** deferred or replayed for time extraction. We assume the first message is rarely a time coordination message, and even if it is, the onboarding process disrupts the flow anyway.
3. The message is simply appended to the deque (truncated to `max_message_length_chars`), and the LLM detects events only for subsequent messages once the user is registered.

> **Why immediate?** We previously waited for a time mention (via regex filter) to ask for timezone. Now that we rely on the LLM and the prefilter is optional, we must onboard users as soon as we see them to ensure the DB is always populated for any potential future event detection.

---

## 9. Integration Notes

Target integration points:
- Telegram: `src/commands/common.py`
- Discord: `src/discord/events.py`

**Threading**: each adapter runs in its own OS thread with its own `asyncio` event loop. They share `message_history`, `chat_locks`, and storage — no conflicts because keys are namespaced by `(platform, chat_id)`. LLM calls are stateless HTTP and work concurrently across both threads.

Message flow:

```
Incoming message
      │
      ▼
[Prefilter enabled?]
      │                    │
     NO                   YES
  (default)                │
      │                    ▼
      │         [regex / keywords check]
      │                    │
      │           ┌────────┴────────┐
      │        match             no match
      │           │                 │
      │           │              ignore msg (LLM not called)
      │           │
      └───────────┘
            │
            ▼  ← both paths (default + prefilter match) reach LLM
  [LLM Event Detector]
            │
      trigger=true?
            │
   ┌────────┴────────┐
  YES                NO
   │                 │
   ▼              ignore msg
[Source TZ resolution]
   │
   ├── event_location non-null ──▶ geocode → IANA TZ ──┐
   │                                                    │
   └── event_location null ──▶ sender DB timezone ──────┤
                                                        ▼
                                          [Transform → Formatter → Reply]
```

---

## 10. Golden Test Cases (Fixtures)

Golden dialogue fixtures are stored at: `tests/fixtures/event_detection_cases.yaml`.

Each case must include expected `trigger`, `polarity`, `times[]`, and optionally `event_location`.

---

## 11. Non-goals (MVP)
- Recurring meetings («каждый вторник»)
- Full participant extraction
- Fallback to regex time extraction if LLM is unavailable (LLM is required for extraction)
- Updating sender's DB timezone from `event_location`
