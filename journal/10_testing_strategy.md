# Technical Spec: Testing Strategy

## 1. Philosophy (MVP)
Мы придерживаемся **Прагматичного подхода**:
1.  **Logic First**: Автоматически тестируем только сложную бизнес-логику (Regex, математика времени).
2.  **Manual UI**: Взаимодействие с Telegram (кнопки, команды) тестируем руками
3.  **Zero External Deps**: Используем стандартную библиотеку `unittest` (или простой `pytest` без сложных плагинов).

---

## 2. Test Pyramid (MVP Scope)

| Layer | Type | Scope | Automation | Tool |
|-------|------|-------|------------|------|
| **L1** | **Unit** | `core/capture.py` (Regex)<br>`core/transform.py` (Time math) | ✅ Automated | `unittest` |
| **L2** | **Integration** | `core/storage.py` (SQLite)<br>`core/geo.py` (API) | ❌ Manual / dev-test | (Run script) |
| **L3** | **E2E / UI** | Bot Commands, Dialogs, Flows | ❌ Manual | Telegram App |

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

### Location:
`tests/test_logic.py`

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
