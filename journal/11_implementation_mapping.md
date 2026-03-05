# Implementation Mapping: Specs → Code

## Philosophy
- **1 Spec ≈ 1 Module** — easy to find code by spec and vice versa
- **Clean Root** — only shared business logic in `src/` root
- **High Cohesion** — everything related to Telegram bot lives inside `src/commands/` (our adapter)

---

## Mapping Table

| Spec | Code File | Responsibility |
|------|-----------|----------------|
| `02_capture_logic.md` | `src/capture.py` | ⚠️ Legacy module — no longer used in main flow. May be repurposed for utilities or removed. |
| `03_transformation_specs.md` | `src/transform.py` | UTC-pivot conversion (now accepts optional `source_tz` override for `event_location`) |
| `05_storage.md` | `src/storage/` | **Package**: SQLite operations (Abstract + Impl) |
| `06_city_to_timezone.md` | `src/geo.py` | Nominatim + TimezoneFinder (also used for `event_location` geocoding) |
| `07_response_format.md` | `src/formatter.py` | Build reply string |
| `08_telegram_commands.md` | `src/commands/` | **Package**: Telegram adapter |
| `09_logging.md` | `src/logger.py` | Logging setup |
| `13_event_detection.md` | `src/event_detection/` | LLM-based event detector: trigger + times[] + event_location |
| `12_discord_integration.md` | `src/discord/` | Discord adapter |
| — | `src/config.py` | Load yaml + .env |
| — | `src/main.py` | Telegram entry point |
| — | `src/discord_main.py` | Discord entry point |

---

## Build Order (Dependencies First)
```
config.py → logger.py → src/storage/ → src/event_detection/ → transform.py → geo.py → formatter.py → src/commands/states.py → src/commands/*.py → main.py
```

> `capture.py` is removed from the build order — no longer part of the main message flow.

---

## Directory Structure
```
Timezone_bot/
├── src/
│   ├── commands/        # TELEGRAM ADAPTER
│   │   ├── __init__.py  # Exposes the main router
│   │   ├── common.py    # /tb_help, Mentions, Kick event
│   │   ├── members.py   # /tb_members, /tb_remove
│   │   ├── settings.py  # /tb_settz, /tb_me
│   │   ├── states.py    # FSM Classes (SetTimezone, RemoveMember)
│   │   └── middleware.py
│   ├── discord/         # DISCORD ADAPTER
│   │   ├── __init__.py  # Bot instance, intents
│   │   ├── commands.py  # Slash command handlers
│   │   ├── ui.py        # Views, Modals (UI components)
│   │   └── events.py    # Message & member events
│   ├── event_detection/ # LLM EVENT DETECTOR
│   │   ├── __init__.py
│   │   ├── detector.py  # LLM call + output parsing
│   │   └── models.py    # Pydantic models for LLM output schema
│   ├── main.py          # Telegram entry
│   ├── discord_main.py  # Discord entry
│   ├── config.py
│   ├── logger.py
│   ├── capture.py       # ⚠️ LEGACY — not used in main flow
│   ├── transform.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── sqlite.py
│   ├── geo.py
│   └── formatter.py
├── tests/
├── journal/
├── configuration.yaml
├── .env
└── env.example
```

---

## Run Command
```bash
./run.sh
# or directly:
uv run python -m src.main
```
