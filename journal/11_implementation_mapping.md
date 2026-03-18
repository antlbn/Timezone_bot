# Implementation Mapping: Specs → Code

## Philosophy
- **1 Spec ≈ 1 Module** — easy to find code by spec and vice versa
- **Clean Root** — only shared business logic in `src/` root
- **High Cohesion** — everything related to Telegram bot lives inside `src/commands/` (our adapter)

---

## Mapping Table

| Spec | Code File | Responsibility |
|------|-----------|----------------|
| — | `src/capture.py` | ❌ **REMOVED** — legacy prefilter no longer used. |
| `03_transformation_specs.md` | `src/transform.py` | UTC-pivot conversion logic. |
| `05_storage.md` | `src/storage/` | **Package**: SQLite operations. Added `pending.py` (Memory layer) and `user_cache.py`. |
| `06_city_to_timezone.md` | `src/geo.py` | Nominatim + TimezoneFinder mapping. |
| `07_response_format.md` | `src/formatter.py` | String formatting and timezone grouping. |
| `08_telegram_commands.md` | `src/commands/` | **Package**: Telegram-side adapter. |
| `09_logging.md` | `src/logger.py` | Project-wide logging setup. |
| `14_llm_module.md` | `src/event_detection/` | **Package**: LLM orchestration. Includes `client.py`, `history.py`, `prompts.py`, and `tools.py`. |
| `12_discord_integration.md` | `src/discord/` | **Package**: Discord-side adapter. |
| — | `src/services/` | **Package**: Shared service layer (e.g., `user_service.py`). |

---

## Build Order (Dependencies First)
```
config.py → logger.py → src/storage/ → src/event_detection/ → src/services/ → transform.py → geo.py → formatter.py → main.py
```

> `capture.py` is removed from the build order — no longer part of the main message flow.

---

## Directory Structure
```
Timezone_bot/
├── src/
│   ├── commands/        # TELEGRAM ADAPTER
│   │   ├── __init__.py  
│   │   ├── common.py    # Help, Text Mentions
│   │   ├── members.py   # /tb_members, /tb_remove
│   │   ├── settings.py  # /tb_settz, /tb_me, DM Onboarding
│   │   ├── states.py    # FSM
│   │   ├── utils.py     # TG-specific UI utils
│   │   └── middleware.py # User registration
│   ├── discord/         # DISCORD ADAPTER
│   │   ├── __init__.py  
│   │   ├── commands.py  # Slash commands
│   │   ├── ui.py        # Views, Modals
│   │   ├── events.py    # on_message, auto-cleanup
│   │   └── tasks.py     # Background sync & prune
│   ├── event_detection/ # LLM PIPELINE
│   │   ├── __init__.py
│   │   ├── detector.py  
│   │   ├── history.py   # Context buffer
│   │   ├── client.py    # API logic
│   │   ├── prompts.py   # System prompts
│   │   └── tools.py     # Action dispatch
│   ├── storage/         # DATA LAYER
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── sqlite.py    # Migrations & SQL
│   │   ├── pending.py   # Frozen messages (Memory)
│   │   └── user_cache.py # LRU caching
│   ├── services/        # BUSINESS LAYER
│   │   └── user_service.py # Multi-platform logic
│   ├── main.py          # TG entry
│   ├── discord_main.py  # Discord entry
│   ├── config.py
│   ├── logger.py
│   ├── transform.py
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
