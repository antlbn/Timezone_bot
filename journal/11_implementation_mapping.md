# Implementation Mapping

This document maps the main specifications to the codebase and shows how the runtime is physically assembled.

It is intended to answer three practical questions:

1. Which spec describes which part of the system?
2. Which files implement that behavior?
3. If the project had to be rebuilt, what should be implemented first?

---

## 1. Top-Level Map

| Spec | Primary Code | What It Owns |
|---|---|---|
| `00_system_context.md` | `src/main.py`, `src/discord_main.py`, `src/commands/`, `src/discord/`, `src/event_detection/`, `src/storage/` | Overall system shape, containers, component boundaries |
| `04_bot_logic.md` | `src/commands/common.py`, `src/commands/settings.py`, `src/discord/events.py`, `src/discord/commands.py` | End-to-end runtime message flow |
| `05_storage.md` | `src/storage/sqlite.py`, `src/storage/base.py`, `src/storage/user_cache.py` | Persistent data model and storage behavior |
| `06_city_to_timezone.md` | `src/geo.py` | City/timezone resolution and manual offset fallback |
| `07_response_format.md` | `src/formatter.py` | Final output rendering rules |
| `03_transformation_specs.md` | `src/transform.py` | Pure time conversion logic |
| `08_telegram_commands.md` | `src/commands/` | Telegram adapter behavior |
| `09_logging.md` | `src/logger.py` | Logging and structured diagnostics |
| `12_discord_integration.md` | `src/discord/` | Discord adapter behavior |
| `14_llm_module.md` | `src/event_detection/__init__.py`, `src/event_detection/detector.py`, `src/event_detection/graph.py` | LLM orchestration and agent runtime |
| `17_llm_memory_model.md` | `src/event_detection/history.py`, `src/event_detection/detector.py`, `src/event_detection/__init__.py` | Memory model: snapshots, thread state, BOT summaries |
| `18_llm_tools.md` | `src/event_detection/graph.py` | Tool contracts: `publish_event`, `update_previous_event` |
| `16_ux_onboarding_spec.md` | `src/commands/settings.py`, `src/commands/common.py`, `src/discord/ui.py`, `src/discord/commands.py` | Onboarding UX, cooldowns, decline behavior |

---

## 2. Codebase by Responsibility

### 2.1 Entry Points

| File | Responsibility |
|---|---|
| `src/main.py` | Telegram bot bootstrap |
| `src/discord_main.py` | Discord bot bootstrap |

### 2.2 Platform Adapters

| Area | Files | Responsibility |
|---|---|---|
| Telegram | `src/commands/common.py`, `src/commands/settings.py`, `src/commands/members.py`, `src/commands/middleware.py` | Group messages, onboarding, commands, passive membership tracking |
| Discord | `src/discord/events.py`, `src/discord/commands.py`, `src/discord/ui.py`, `src/discord/tasks.py` | Guild messages, onboarding UI, slash commands, maintenance tasks |

### 2.3 Event Detection Core

| File | Responsibility |
|---|---|
| `src/event_detection/__init__.py` | `process_message(...)`, aging, snapshotting, orchestration |
| `src/event_detection/detector.py` | `detect_event(...)`, mode switching, callbacks, normalization |
| `src/event_detection/graph.py` | LangGraph nodes, tool schemas, action execution |
| `src/event_detection/history.py` | In-memory short-term history and per-chat locks |
| `src/event_detection/prompts.py` | System prompt and tool behavior guidance |
| `src/event_detection/client.py` | Model selection and provider setup |

### 2.4 Deterministic Domain Logic

| File | Responsibility |
|---|---|
| `src/transform.py` | Parse and convert times |
| `src/formatter.py` | Render conversion results |
| `src/geo.py` | Resolve city or manual time into timezone |

### 2.5 Data Layer

| File | Responsibility |
|---|---|
| `src/storage/sqlite.py` | Main SQLite implementation |
| `src/storage/base.py` | Storage interface |
| `src/storage/user_cache.py` | In-memory LRU snapshot cache |
| `src/storage/pending.py` | Invite cooldown state only |

### 2.6 Shared Service Layer

| File | Responsibility |
|---|---|
| `src/services/user_service.py` | Shared user/member lookup logic used by adapters |

---

## 3. Runtime Dependency Chain

The runtime flow is best understood in this order:

```text
config.py
  -> logger.py
  -> storage/
  -> platform adapters (commands/ , discord/)
  -> event_detection/
  -> geo.py / transform.py / formatter.py
  -> main.py / discord_main.py
```

More specifically for message processing:

```text
Platform Adapter
  -> process_message(...)
  -> detect_event(...)
  -> LangGraph action node
  -> formatter / transform / geo / storage
  -> platform send/edit/delete callback
```

---

## 4. Directory Structure

```text
Timezone_bot/
├── src/
│   ├── commands/          # Telegram adapter
│   ├── discord/           # Discord adapter
│   ├── event_detection/   # LLM agent runtime
│   ├── services/          # Shared service helpers
│   ├── storage/           # SQLite + in-memory cache/cooldown helpers
│   ├── config.py
│   ├── logger.py
│   ├── transform.py
│   ├── geo.py
│   ├── formatter.py
│   ├── main.py
│   └── discord_main.py
├── tests/
├── journal/
├── configuration.yaml
└── uv.lock
```

---

## 5. Rebuild Order

If only the specs remained and the system had to be recreated, implement in this order:

### Stage 1. Foundations

1. `config.py`
2. `logger.py`
3. `storage/base.py`
4. `storage/sqlite.py`
5. `storage/user_cache.py`

### Stage 2. Deterministic domain logic

6. `transform.py`
7. `geo.py`
8. `formatter.py`

### Stage 3. Agent core

9. `event_detection/history.py`
10. `event_detection/prompts.py`
11. `event_detection/client.py`
12. `event_detection/graph.py`
13. `event_detection/detector.py`
14. `event_detection/__init__.py`

### Stage 4. Platform adapters

15. Telegram adapter: `src/commands/`
16. Discord adapter: `src/discord/`

### Stage 5. Entrypoints and operations

17. `src/main.py`
18. `src/discord_main.py`
19. background tasks / cleanup / maintenance logic
20. test suite

---

## 6. Where To Look

### “Why did the bot respond to this message?”

Start with:

- `src/commands/common.py` or `src/discord/events.py`
- then `src/event_detection/__init__.py`
- then `src/event_detection/detector.py`
- then `src/event_detection/graph.py`

### “Why didn’t the bot respond?”

Check:

- onboarding / registration gate,
- `max_message_age` guard in `process_message(...)`,
- absence of valid `points`,
- missing chat members in storage,
- sender with no timezone.

### “Why did the bot edit instead of publish?”

Check:

- `update_previous_event` handling in `src/event_detection/graph.py`
- distance-based edit/republish logic

### “Where is chat memory?”

Two places:

- `src/event_detection/history.py` for process-local short-term context
- `data/graph_checkpoints.db` via LangGraph for persisted thread state

---

## 7. Current Invariants

The codebase currently assumes:

1. No regex prefilter before the LLM pipeline.
2. Unregistered users trigger detection-only onboarding logic.
3. Old messages are not replayed after onboarding.
4. Per-chat LLM execution is serialized.
5. Time extraction is probabilistic/LLM-driven, but conversion/rendering is deterministic.

If a future refactor breaks any of these, the docs in `04`, `14`, `16`, `17`, and `18` should be updated together.
