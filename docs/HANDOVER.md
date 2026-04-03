# Handover: Intentional Decisions

This document is the short reasoning layer above the specs. The canonical source of truth is `journal/`. `HANDOVER.md` should explain what was chosen, why it was chosen, and which trade-offs were accepted for MVP.

For setup and local run instructions, see [ONBOARDING.md](ONBOARDING.md).

## 1. Source of Truth

- `journal/*.md` is canonical for product and runtime behavior.
- `HANDOVER.md` is intentionally shorter and more opinionated.
- If this file and `journal` ever disagree, `journal` wins.

Practical rule:
- short architectural intent belongs here,
- exact runtime rules and edge cases belong in `journal`.

## 2. Core Architecture

The system is built as thin platform adapters around one shared core:

```text
Telegram adapter ─┐
                  ├─> shared core -> formatted reply
Discord adapter ──┘
```

Shared core modules:
- `event_detection` — one-shot LLM orchestration and validation
- `geo` — city/place → IANA timezone resolution
- `transform` — UTC-pivot time conversion
- `formatter` — human-readable reply rendering
- `storage` — SQLite persistence + in-memory caches
- `services` — cross-platform user logic
- `onboarding / pending queue` — frozen message lifecycle

The key boundary is intentional:
- the LLM does not send replies,
- the LLM returns structured detection only,
- shared bot logic decides whether conversion is allowed,
- Telegram and Discord are delivery and UX adapters.

## 3. Main Decisions

### 3.1 UTC Pivot for All Conversions

All conversions go through UTC:

```text
source local time -> source timezone -> UTC -> target timezone
```

Why:
- it avoids direct zone-to-zone arithmetic,
- it keeps DST handling aligned with IANA timezone data,
- it gives one canonical transformation path for every platform.

### 3.2 One-Shot LLM Detection

In this branch, event detection is intentionally `one-shot`: the LLM sees the current message plus anchor timestamp, not a rolling chat history.

Why:
- smaller and more predictable runtime contract,
- easier validation of structured output,
- lower prompt complexity and less hidden state,
- easier to reason about failures and reproduce behavior.

Important context:
- I did think about and experiment with passing several previous messages to the LLM.
- That work evolved into an alternative LangGraph-based version in another branch.
- For this branch, I intentionally kept the detector at the simpler `one-shot / one-message` level.

### 3.3 LLM Over Regex

The MVP uses LLM-only detection and does not keep a regex fallback in the canonical path.

Why:
- natural language time mentions are too varied for a clean regex-first design,
- the LLM can return a strict JSON contract instead of raw text,
- one structured detector is easier to keep platform-agnostic than parallel heuristic pipelines.

### 3.4 Lazy Onboarding Instead of Forced Setup

Timezone setup starts only when a user actually triggers a time-coordination event.

Why:
- lower chat pollution,
- no need to force setup before first value,
- original actionable messages can be frozen and replayed after setup,
- this matches the product goal better than command-first onboarding.

Related runtime choice:
- pending messages are kept in short-lived in-memory storage,
- if onboarding succeeds, the frozen message is replayed,
- if the user declines or times out, the message is discarded unless explicit source location makes conversion possible.

### 3.5 Passive Membership Collection

The bot knows only members it has actually observed in the chat.

Why:
- Telegram cannot reliably act as a full member directory without stronger permissions and extra coupling,
- passive collection keeps the MVP deployable with less setup,
- conversion output stays scoped to known members of the current chat.

Accepted limitation:
- lurkers do not appear in conversions by design.

### 3.6 Chat Membership Is Separate from User Profile

Membership deletion is chat-scoped. User profile data is not treated as disposable chat-local state.

Why:
- the same user may exist across chats and platforms,
- removing someone from one chat should not destroy their saved timezone,
- storage stays aligned with the domain split: `users` vs `chat_members`.

Practical consequence:
- Telegram manual cleanup such as `/tb_remove` should remove the membership link for that group, not erase the whole user record.
- When the bot is removed from a chat/server, it should clear membership for that chat/server only.

### 3.7 SQLite Plus Small In-Memory State

The MVP uses one SQLite database plus a few small runtime caches and buffers.

Current local runtime state:
- user snapshot cache,
- chat-members cache,
- frozen onboarding messages.

Why:
- zero external infrastructure for review and local run,
- good enough for a single-process MVP,
- easier debugging and handover than introducing Redis or a larger state stack too early.

### 3.8 Low-Friction Geocoding for MVP

The current geo path is intentionally simple: geocoding plus timezone resolution to produce an IANA timezone.

Terminology note:
- `tz_city` is the detector field for source-location text attached to a time point.
- It does not mean "user city".
- It means "the place that defines the source timezone for this specific message", for example `London` in `"12:00 in London"` or `Berlin` in `"7pm Berlin time"`.

Why:
- enough for onboarding and message-level source overrides,
- keeps the durable profile value clean: only IANA timezone is stored,
- avoids adding disambiguation UX and provider-specific complexity in MVP.

Important constraint:
- location text from a message is a one-message override only; it must not overwrite stored user timezone.

### 3.9 AM/PM Ambiguity: Publish with Annotation, Not Silence

When the LLM cannot determine whether a bare hour is AM or PM, the bot publishes the conversion with an `AM/PM?` prefix on the source line rather than staying silent.

The three states:

| `time_mentioned` | `am_pm_clear` | Bot behavior |
|---|---|---|
| `false` | — | stay silent |
| `true` | `true` | convert and publish normally |
| `true` | `false` | publish with `AM/PM?` on the source line |

Ambiguity rule (working-hours heuristic, `06:00–22:00`):
- bare hour `1–5` → choose PM, mark clear
- bare hour `6–10` → both AM and PM fall inside working hours → ambiguous
- bare hour `11–12` → choose AM, mark clear

Why:
- silence on ambiguous times would hide coordination events entirely; the user gets no feedback.
- the annotation signals uncertainty without blocking the reply.
- a mixed message with both clear and ambiguous points publishes both; only ambiguous ones get the annotation.

### 3.10 Dual-Timezone Reduction

When one moment is expressed in two timezones in the same message (e.g., `"в 3 по мск, это 4 по Вене"`), the LLM keeps only the last target zone.

Example: `"в 3 по мск, это 4 по Вене"` → `time=04:00`, `tz_city=Vienna`

Why:
- the second zone is the user's explicit restatement in a more useful timezone; it is the intended source for conversion.
- keeping both would create a redundant or contradictory output.

### 3.11 Promptfoo Evaluation & Model Selection

Model choices for event detection were deeply evaluated using `promptfoo` across edge cases, multilingual inputs, and ambiguous phrasing.

Results and insights:
- **Llama 4B**: Struggled significantly. Often hallucinated JSON structures, missed implicit `am_pm_clear` rules, and failed on complex relative time contexts.
- **Llama 3.1 8B**: Performed much better. Reliable enough to serve as the default fallback option when primary APIs fail.
- **Nemotron (e.g. 4 12B)**: Excellent accuracy, handling complex prompt contracts flawlessly.
- **Gemini Flash Lite (3.1/2.0)**: Very fast, extraordinarily reliable, and perfectly aligned with the JSON extraction rules. Selected as the primary LLM for the MVP.

## 4. Known Limits

- The bot is intentionally `known-members only`; it does not infer silent participants.
- Frozen onboarding messages are in-memory only and do not survive process restart.
- This branch does not use multi-message LLM context in the canonical flow.
- Telegram and Discord use different UX surfaces, but they are expected to preserve the same core business rules.

## 5. If I Had More Time

- I would evaluate alternative geocoding strategies/providers instead of treating the current choice as final.
- I would revisit richer multi-message detection, but only if it improved accuracy enough to justify the extra runtime complexity. That line of thinking already led to a separate LangGraph-based branch; it was intentionally not merged into this simpler MVP path.

## 6. Canonical Specs

Start here when changing behavior:
- [01_scope_and_MVP.md](../journal/01_scope_and_MVP.md)
- [00_c4.md](../journal/00_c4.md)
- [03_transformation_specs.md](../journal/03_transformation_specs.md)
- [04_bot_logic.md](../journal/04_bot_logic.md)
- [05_storage.md](../journal/05_storage.md)
- [06_city_to_timezone.md](../journal/06_city_to_timezone.md)
- [13_configuration.md](../journal/13_configuration.md)
- [14_llm_module.md](../journal/14_llm_module.md)
- [15_onboarding_capture.md](../journal/15_onboarding_capture.md)
