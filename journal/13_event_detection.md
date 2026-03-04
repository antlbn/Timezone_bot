# Technical Spec: Event Detection (LLM Layer)

## 1. Overview (MVP v1)

This module detects whether a chat dialogue contains a **practically useful time mention** (for coordination / availability / meeting) and produces a **strict JSON** payload that acts as a **binary trigger**:

- Should the bot **react** to the detected time(s) (run conversion, script, etc.)?
- Or should it **ignore** this message window?

We deliberately keep MVP v1 simple:
- No extraction of final datetime, timezone, or “confirmed vs tentative” hierarchy.
- LLM only decides: **trigger / no trigger** and whether the mention is **positive** (useful) or **negative** (irrelevant / past / refusal / personal only).

This is an **additional layer** to the existing MVP stack:
- Strict Regex capture (`02_capture_logic.md`)
- UTC-pivot time conversion (`03_transformation_specs.md`)
- User timezone storage (IANA in SQLite, `05_storage.md`)

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

### 2.2 Sender Context (DB Default)
From storage (`05_storage.md`), for the sender of the newest message in the window:
- `sender_timezone_iana`: IANA name (e.g. `Europe/Berlin`)
- Optional: `sender_city`, `sender_flag` (for debugging / future UX)

### 2.3 Anchor Time
- `anchor_timestamp_utc`: timestamp of the newest message in the window

Used to resolve relative expressions: “завтра”, “в понедельник”, “через 2 часа”.

---

## 3. Output Contract (MVP v1)

### 3.1 Top-level shape (strict JSON)
LLM MUST output JSON only (no prose), matching:

```json
{
  "trigger": true,
  "polarity": "positive",
  "confidence": 0.0,
  "reason": ""
}
```

Fields:
- `trigger: bool`
  - `true` → bot **should** react (run conversion/script) to times detected by regex.
  - `false` → bot **should ignore** this message window.
- `polarity: "positive" | "negative"`
  - `positive` → time mention is useful for coordination / availability / joint work.
  - `negative` → time mention is past, refusal, purely personal, or otherwise irrelevant.
- `confidence: float [0,1]`
  - Model’s self-estimated confidence in this decision.
- `reason: string`
  - Short free-text explanation (RU/EN) for logs and debugging.

### 3.2 JSON Schema file
Formal JSON Schema is stored at: `journal/13_event_detection.schema.json`.

---

## 4. Decision Policy (MVP v1)

### 4.1 When to set `trigger = true` (positive)

Set `trigger=true`, `polarity="positive"` when the time mention is **practically useful** for others in the chat, for example:

- Joint meetings / calls / events:
  - “завтра в 14:00 созвон”
  - “встретимся в 19:00”
  - “Ivan wants to meet tomorrow in 15:30 for all crew”
- Time windows of **availability for others**:
  - “если я завтра буду с заказчиком в 8:00, смогу у него спросить”
  - “я смогу в 10 и в 14:00, выбирайте”

LLM **не возвращает времена** — список конкретных таймстрок остаётся задачей regex-слоя (`extract_times`).  
Если `trigger=true`, приложение дальше просто использует уже найденные `times` (один или несколько, как сейчас).

### 4.2 When to set `trigger = false` (negative)

Set `trigger=false`, `polarity="negative"` when:

- **Past references**:
  - “я вчера в 8 уже спал”
  - “вчера был в музее в 2”
- **Отказ / недоступность**:
  - “I cannot be on the meeting in 15:30”
  - “завтра в 8 и в 18 буду на спорте”
- **Личные планы, не влияющие на других**:
  - “я завтра пойду погуляю с собакой”
  - “завтра в 8 у меня тренировка”
- **Вопросы без решения**:
  - “как думаете во сколько нужно созвониться?”
  - “в 8:00 по Лондону?” (если в окне нет явного решения/фиксации)

В спорных случаях (непонятно, полезно или нет) модель должна **предпочитать `trigger=false`**, чтобы бот не “стрелял” слишком часто.

---

## 5. Prefilter Logic (Regex + Keywords)

The LLM layer should not be called for every message. Instead we use a **prefilter**:

1. **Strict time regex** (from `02_capture_logic.md` / `capture.patterns`)
2. **Numeric candidate regex** (`event_detection.numeric_candidate_pattern`)
3. **Keywords** (RU/EN) in the current or nearby messages

### 5.1 Keywords

Keywords are configured in `configuration.yaml` and are split by language:

- Russian examples:
  - `созвон`, `встреч`, `бронь`, `мит`, `перенес`, `перенос`, `собрание`
  - `завтра`, `сегодня`, `послезавтра`, `утром`, `вечером`
- English examples:
  - `call`, `meeting`, `meet`, `sync`, `standup`, `stand-up`
  - `tomorrow`, `today`, `tonight`, `morning`, `evening`, `resched`, `reschedule`

Exact lists live in `event_detection.prefilter.keywords_ru` and `event_detection.prefilter.keywords_en`.

### 5.2 Prefilter Decision

LLM is called if:

- **any strict time match** is found, OR
- **any numeric candidate match** is found AND there is at least one relevant keyword (RU or EN) in the current or recent messages.

If neither strict matches nor (candidate + keywords) are present → we skip LLM for this window.

### 5.3 Confidence & Extended Context

Basic algorithm:

1. Collect last `context_window_messages` messages for the chat.
2. Run prefilter; if it says “no signal” → `trigger=false` (LLM not called).
3. Call LLM once with this window.
4. If the model returns `confidence < min_confidence_trigger`:
   - Optionally extend the context (e.g. include a few more previous messages up to some hard limit) and re-run once.
5. If **after all attempts** confidence is still `< min_confidence_trigger`:
   - Force `trigger=false` (silence is safer).

---

## 6. Configuration (`configuration.yaml`)

Add / update section:

```yaml
event_detection:
  enabled: true
  context_window_messages: 8

  prefilter:
    require_time_regex_or_keywords: true
    keywords_ru:
      - "созвон"
      - "встреч"
      - "бронь"
      - "мит"
      - "митинг"
      - "созван"
      - "завтра"
      - "сегодня"
      - "послезавтра"
      - "утром"
      - "вечером"
      - "перенес"
      - "перенос"
      - "по лондону"
      - "по москве"
    keywords_en:
      - "call"
      - "meeting"
      - "meet"
      - "sync"
      - "standup"
      - "stand-up"
      - "stand up"
      - "tomorrow"
      - "today"
      - "tonight"
      - "morning"
      - "evening"
      - "resched"
      - "reschedule"
      - "utc"
      - "mst"
      - "est"
      - "pst"

  # Regex for numeric candidate hours (used only for LLM prefilter)
  numeric_candidate_pattern: '\b([0-1]?[0-9]|2[0-3])\b'

  # Treat as trigger only if confidence >= threshold
  min_confidence_trigger: 0.75
```

Notes:
- Provider credentials must be stored in environment variables (not in YAML).
- Prefilter exists to avoid calling LLM on every message.

---

## 7. Integration Notes (High Level)

Target integration points:
- Telegram: `src/commands/common.py` (current time mention handler)
- Discord: `src/discord/events.py` (message handler)

Behavior:
- If `trigger == false`: do not run conversion / script for this window.
- If `trigger == true`: run existing flow (regex times → conversion → formatter / script).

---

## 8. Golden Test Cases (Fixtures)

Golden dialogue fixtures are stored at: `tests/fixtures/event_detection_cases.yaml`.

The detector must match expected `trigger` / `polarity` for each case.

---

## 9. Non-goals (MVP)
- Recurring meetings (“каждый вторник”)
- Full participant extraction
- Robust location resolution beyond basic timezone hints

