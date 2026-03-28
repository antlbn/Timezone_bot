# 01. Scope and MVP Specification

> Canonical product specification for MVP scope, boundaries, and completion criteria.

## 1. Product Goal

Reduce friction when coordinating time in group chats with participants in different timezones by automatically showing local time for known participants.

## 2. Product Mission

The bot watches normal chat conversation in Telegram groups and Discord servers.
When someone mentions a time coordination event, the bot detects it, interprets the source time, and replies with a readable conversion for known members of that chat.

## 3. Core Principles

- **MVP-first**: Anything not required for the main coordination scenario is out of scope.
- **Spec-driven**: The `journal/*.md` files are the primary source of truth for product and architecture.
- **LLM-only detection**: Time-event detection and extraction are performed only by the LLM pipeline.
- **IANA-only timezone storage**: Persistent user timezone is stored only as an IANA timezone name.
- **Low chat pollution**: Shared chats should remain clean; private chat is used only for onboarding.
- **Rebuildable from specs**: The specification set must be sufficient to restore the system even if the code is lost.

## 4. MVP Scope

### In Scope

- Telegram group chats.
- Discord servers.
- Passive member discovery from incoming messages.
- Per-user timezone storage.
- LLM-based detection of time coordination events from ordinary messages.
- Extraction of one or more time points and optional `event_location`.
- Conversion and reply for known members of the current chat only.
- Private onboarding flow for unknown authors who trigger a time event.
- Auto-cleanup of short-lived system messages in shared chats.

### Out of Scope

- Recurring events such as "every Tuesday at 10".
- Calendar integrations.
- Extraction of a subset of participants from message text.
- Full private-chat product mode.
- Persistent conversation history for the LLM.
- Numeric UTC offsets as durable user settings.
- Regex fallback when LLM is unavailable.

## 5. Supported Platforms

| Platform | Shared chat scope | Private chat scope |
|---|---|---|
| Telegram | Group chats | Onboarding only |
| Discord | Servers | Onboarding only |

Private chat is not a standalone use mode. It exists only to complete onboarding and timezone setup with minimal noise in shared chats.

## 6. Primary User Story

1. Users discuss a meeting in a group chat or server.
2. A participant writes a message containing a time coordination event.
3. The bot sends the message context to the LLM.
4. If the LLM returns `trigger=false`, the bot stays silent.
5. If the LLM returns `trigger=true`, the bot determines the source timezone:
   - sender timezone from DB, or
   - `event_location` resolved to a timezone.
6. The bot converts the time for known members of that chat.
7. The bot replies with a compact, readable list grouped by timezone/location.

## 7. Registration and Conversion Rules

### 7.1 Registered Author

If the author has a stored timezone, a detected event is processed normally.

### 7.2 Unregistered Author

If the author does not have a stored timezone and the LLM detects a coordination event:

1. The message is frozen in the pending queue.
2. The onboarding flow starts asynchronously.
3. The original processing path is locked until one of three outcomes happens:
   - onboarding completed,
   - onboarding explicitly declined,
   - onboarding timed out / ignored.

### 7.3 Outcomes for Unregistered Author

| Outcome | DB effect | Pending message result |
|---|---|---|
| Onboarding completed | Save user's IANA timezone | Release and process the frozen message |
| Onboarding declined | Save a decline flag | Release the frozen message only if `event_location` allows conversion without sender TZ; otherwise discard |
| Onboarding ignored / timeout | No timezone saved; cooldown still applies | Pending lock expires and the frozen message is discarded |

### 7.4 Event Location Override

`event_location` is a one-time source-time override for the current message.

Rules:
- It never updates the sender's stored timezone.
- It allows conversion even if the author refused onboarding or has no saved timezone.
- Example: `"12:00 in London"` may be converted without sender registration.
- Example: plain `"12:00"` from an unregistered or declined user must not be converted.

## 8. Membership and Display Rules

- The bot shows conversion only for **known members** of the current chat.
- Unknown participants are not inferred or added from message text.
- Lurkers who never wrote messages are absent from the output by design.
- If only one known user is available, the response may contain only that user/timezone group.

## 9. High-Level Architecture

```
Telegram Adapter ─┐
                  ├─> Shared Core -> Reply
Discord Adapter ──┘

Shared Core:
- event_detection
- storage
- geo
- transform
- formatter
- onboarding / pending queue
```

Detailed architecture is defined in [00_c4.md](/Users/johnwunderbellen/Timezone_bot/journal/00_c4.md).

## 10. Configuration Expectations

The system is configured through `.env` and `configuration.yaml`.

Expected MVP controls:
- platform tokens,
- cleanup TTL for system messages,
- onboarding timeout,
- onboarding cooldown,
- LLM settings,
- response display limits,
- message age / length safety limits.

## 11. Completion Criteria

The project is considered complete for MVP when all conditions below are true.

### 11.1 Product Done

- Telegram groups are supported end-to-end.
- Discord servers are supported end-to-end.
- Registered users get correct conversions in normal group/server conversation.
- Unknown users who trigger a time event are invited to onboarding without polluting the shared chat.
- Successful onboarding releases the frozen message and posts the delayed conversion.
- Declined or ignored onboarding does not create broken or stale replies.
- Explicit `event_location` works as a source-time override.

### 11.2 Specification Done

- The specification set is internally consistent.
- Scope, behavior, storage, integrations, and runtime flow are documented.
- A new engineer can rebuild the system from the specs without relying on existing code.
- C4 diagrams exist for system context and containers, plus at least one dynamic flow.

### 11.3 Quality Done

- Core behavior is covered by automated tests.
- Major edge cases and non-goals are explicitly documented.
- Operational limits and configurable timers are documented.
- The implementation can be run and configured without tribal knowledge.

## 12. Specification Quality Standard

The specification set should satisfy these qualities:

1. **Recoverability**: If the entire codebase is lost, the project can be rebuilt from the specs with acceptable effort.
2. **Consistency**: No contradictory behavior across product, storage, onboarding, and platform specs.
3. **Compactness**: Each spec is focused and avoids duplicated narrative.
4. **Readability**: Important decisions, rules, and flows are easy to scan.

## 13. Source of Truth Map

- [00_c4.md](/Users/johnwunderbellen/Timezone_bot/journal/00_c4.md): architecture diagrams
- [02_domain_model.md](/Users/johnwunderbellen/Timezone_bot/journal/02_domain_model.md): domain entities, states, and invariants
- [04_bot_logic.md](/Users/johnwunderbellen/Timezone_bot/journal/04_bot_logic.md): runtime processing rules
- [05_storage.md](/Users/johnwunderbellen/Timezone_bot/journal/05_storage.md): persistence rules
- [06_city_to_timezone.md](/Users/johnwunderbellen/Timezone_bot/journal/06_city_to_timezone.md): location resolution
- [08_telegram_commands.md](/Users/johnwunderbellen/Timezone_bot/journal/08_telegram_commands.md): Telegram-specific UX
- [12_discord_integration.md](/Users/johnwunderbellen/Timezone_bot/journal/12_discord_integration.md): Discord-specific UX
- [14_llm_module.md](/Users/johnwunderbellen/Timezone_bot/journal/14_llm_module.md): LLM contract and orchestration
- [16_ux_onboarding_spec.md](/Users/johnwunderbellen/Timezone_bot/journal/16_ux_onboarding_spec.md): onboarding UX details
