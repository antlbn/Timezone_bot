# Implementation Mapping: Specs → Code

## Philosophy
- **1 Spec ≈ 1 Module** — легко найти код по спеку и наоборот
- **Flat Structure** — все файлы в `src/`, без глубокой вложенности
- **Small Files** — каждый модуль ~50-150 строк

---

## Mapping Table

| Spec | Code File | Responsibility |
|------|-----------|----------------|
| `02_capture_logic.md` | `src/capture.py` | Regex time extraction |
| `03_transformation_specs.md` | `src/transform.py` | UTC-pivot conversion |
| `05_storage.md` | `src/storage.py` | SQLite operations |
| `06_city_to_timezone.md` | `src/geo.py` | Nominatim + TimezoneFinder |
| `07_response_format.md` | `src/formatter.py` | Build reply string |
| `08_telegram_commands.md` | `src/commands.py` | All `/tb_*` handlers |
| `09_logging.md` | `src/logger.py` | Logging setup |
| — | `src/config.py` | Load yaml + .env |
| — | `src/main.py` | Entry point |

---

## Build Order (Dependencies First)
```
config.py → logger.py → storage.py → capture.py → transform.py → geo.py → formatter.py → commands.py → main.py
```

---

## Directory Structure
```
Timezone_bot/
├── src/
│   ├── main.py
│   ├── config.py
│   ├── logger.py
│   ├── capture.py
│   ├── transform.py
│   ├── storage.py
│   ├── geo.py
│   ├── formatter.py
│   └── commands.py
├── tests/
│   ├── test_capture.py
│   └── test_transform.py
├── journal/           # Specs
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
