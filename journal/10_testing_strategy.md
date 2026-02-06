# Technical Spec: Testing Strategy

## 1. Philosophy (MVP)
Мы придерживаемся **Прагматичного подхода**:
1.  **Logic First**: Автоматически тестируем только сложную бизнес-логику (Regex, математика времени).
2.  **Manual UI**: Взаимодействие с Telegram (кнопки, команды) тестируем руками
3.  **Zero External Deps**: Используем стандартную библиотеку `unittest` (или простой `pytest` без сложных плагинов).

---

## 2. Test Pyramid (Telegram + Discord)

| Layer | Type | Scope | Automation | Tool |
|-------|------|-------|------------|------|
| **L1** | **Unit** | `src/capture.py` (Regex)<br>`src/transform.py` (Time math)<br>`src/geo.py` (Geocoding) | ✅ Automated | `pytest` |
| **L1.5** | **Handlers** | `src/commands/*.py` (Telegram)<br>`src/discord/commands.py` (Discord) | ✅ Automated | `pytest` + `mock` |
| **L2** | **Integration** | `src/storage/`, `middleware`, events | ✅ Automated | `pytest` |
| **L3** | **E2E / UI** | Bot Commands, Dialogs, Flows | ❌ Manual | Telegram App, Discord |


---

## 3. Automated Logic Tests (L1)

Эти тесты должны запускаться перед каждым коммитом.

### Scope:
1.  **Capture Patterns**:
    -   Проверка всех примеров из `configuration.yaml`
    -   Edge cases (нет времени, мусор, "цена 500")
2.  **Transformation Logic**:
    -   Конвертация UTC → Target TZ
    -   Обработка смены дня (Day +1 / -1)
    -   Форматирование строки ответа
3.  **Resilience (L2)**:
    -   Обработка ошибок API (Geo timeout)
    -   Устойчивость базы данных (Middleware catch)
    -   Парсинг мусорных данных
4.  **Handlers (L1.5)**:
    -   Unit-тесты команд (`cmd_me`, `cmd_settz`)
    -   Mocking `aiogram.types.Message` и `storage`
    -   Проверка вызова `message.answer` с ожидаемым текстом

### Location:
- `tests/test_capture.py` — Regex patterns
- `tests/test_transform.py` — UTC-pivot logic
- `tests/test_formatter.py` — Reply formatting
- `tests/test_geo.py` — Geocoding and timezone resolution
- `tests/test_storage.py` — Database operations (platform separation)
- `tests/test_handlers.py` — Telegram handlers
- `tests/test_discord_handlers.py` — Discord handlers
- `tests/test_discord_events.py` — Discord events (auto-cleanup)
- `tests/test_exceptions_logging.py` — Error handling

---

## 4. Manual Verification Logic (L2 & L3)

Для проверки интеграций и UI используем чек-лист (`task.md` Phase 4).

**Ключевые сценарии:**
1.  **Startup**: Бот запускается, БД создается.
2.  **New User Flow**: `/tb_settz` → ввод города → сохранение.
3.  **Group Chat**:
    -   Юзер А (Berlin) пишет "15:00"
    -   Юзер Б (NY) видит "09:00 New York"
4.  **Error Handling**: Ввод несуществующего города (должен быть fallback).

---

## 5. Continuous Integration (Future)
В будущем (Post-MVP) добавить GitHub Actions:
- Linting (`ruff`)
- Running tests (`python -m unittest discover tests`)

---

## 6. База данных в тестах
**Важно:** Для запуска тестов **не нужен** файл `data/bot.db`.
- **L1.5 (Handlers)**: Используют `unittest.mock` (вообще не трогают диск).
- **L2 (Integration)**: Тесты `test_storage.py` автоматически создают и удаляют **временный файл БД** (`tests/test_bot.db`).
Это гарантирует, что тесты можно запускать на чистой машине сразу после `git clone`.
