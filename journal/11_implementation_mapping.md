# Implementation Mapping: Specs → Code

## Philosophy
- **1 Spec ≈ 1 Module** — легко найти код по спеку и наоборот
- **Clean Root** — в корне `src/` только общая бизнес-логика
- **High Cohesion** — всё, что касается Telegram-бота, лежит внутри `src/commands/` (это наш адаптер)

---

## Mapping Table

| Spec | Code File | Responsibility |
|------|-----------|----------------|
| `02_capture_logic.md` | `src/capture.py` | Regex time extraction |
| `03_transformation_specs.md` | `src/transform.py` | UTC-pivot conversion |
| `05_storage.md` | `src/storage/` | **Package**: SQLite operations (Abstract + Impl) |
| `06_city_to_timezone.md` | `src/geo.py` | Nominatim + TimezoneFinder |
| `07_response_format.md` | `src/formatter.py` | Build reply string |
| `08_telegram_commands.md` | `src/commands/` | **Package**: All Telegram handling logic |
| `09_logging.md` | `src/logger.py` | Logging setup |
| — | `src/config.py` | Load yaml + .env |
| — | `src/main.py` | Entry point |

---

## Build Order (Dependencies First)
```
config.py → logger.py → src/storage/ → capture.py → transform.py → geo.py → formatter.py → src/commands/states.py → src/commands/*.py → main.py
```

---

## Directory Structure
```
Timezone_bot/
├── src/
│   ├── commands/        # TELEGRAM ADAPTER (Cohesive Module)
│   │   ├── __init__.py  # Exposes the main router
│   │   ├── common.py    # /tb_help, Mentions, Kick event
│   │   ├── members.py   # /tb_members, /tb_remove
│   │   ├── settings.py  # /tb_settz, /tb_me
│   │   ├── states.py    # FSM Classes (SetTimezone, RemoveMember)
│   │   └── middleware.py # Middleware specific to this bot
│   ├── main.py
│   ├── config.py
│   ├── logger.py
│   ├── capture.py
│   ├── transform.py
│   ├── storage/         # Storage Package
│   │   ├── __init__.py  # Singleton export
│   │   ├── base.py      # Abstract Interface
│   │   └── sqlite.py    # Implementation
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
