# Implementation Mapping: Specs → Code

## Philosophy
- **1 Spec ≈ 1 Module** — easy to find code by spec and vice versa
- **Clean Root** — only shared business logic in `src/` root
- **High Cohesion** — everything related to Telegram bot lives inside `src/commands/` (our adapter)

---

## Mapping Table

| Spec | Code File | Responsibility |
|------|-----------|----------------|
| `02_capture_logic.md` | `src/capture.py` | Regex time extraction |
| `03_transformation_specs.md` | `src/transform.py` | UTC-pivot conversion |
| `05_storage.md` | `src/storage/` | **Package**: SQLite operations (Abstract + Impl) |
| `06_city_to_timezone.md` | `src/geo.py` | Nominatim + TimezoneFinder |
| `07_response_format.md` | `src/formatter.py` | Build reply string |
| `08_telegram_commands.md` | `src/commands/` | **Package**: Telegram adapter |
| `09_logging.md` | `src/logger.py` | Logging setup |
| `13_event_detection.md` | `src/event_detection/` (planned) | LLM-based scheduling detector + strict JSON |
| `12_discord_integration.md` | `src/discord/` | Discord adapter |
| — | `src/config.py` | Load yaml + .env |
| — | `src/main.py` | Telegram entry point |
| — | `src/discord_main.py` | Discord entry point |

---

## Build Order (Dependencies First)
```
config.py → logger.py → src/storage/ → capture.py → event_detection (planned) → transform.py → geo.py → formatter.py → src/commands/states.py → src/commands/*.py → main.py
```

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
│   ├── main.py          # Telegram entry
│   ├── discord_main.py  # Discord entry
│   ├── config.py
│   ├── logger.py
│   ├── capture.py
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
