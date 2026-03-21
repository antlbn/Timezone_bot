# 🚀 LangSmith: Быстрый старт

## Шаг 1 — Загрузить тест-кейсы

```bash
uv run python tests/langsmith/create_curated_cases.py
```

Создаёт датасет **`timezone-bot-tool-calls`** с 7 готовыми примерами.

---

## Шаг 2 — Запустить eval

```bash
uv run python tests/langsmith/run_eval.py
```

Агент прогоняется по каждому примеру. В конце — короткий итог в терминале и ссылка в UI.

---

## Шаг 3 — Смотреть результаты в UI

Открой: **https://eu.smith.langchain.com** → проект **timezone-bot-tests** → вкладка **Experiments**

Там по каждому примеру видно:

| Метрика | Что проверяет |
|---|---|
| `event_detected` | ✅/❌ bot ответил event=true/false правильно |
| **`correct_tool`** | ✅/❌ вызван нужный tool (publish / update / ничего) |
| `tool_called` | ✅/❌ при event=true хоть какой tool был вызван |
| `time_extracted` | ✅/❌ извлечено правильное время (HH:MM) |

---

## Добавить новый тест-кейс

Открой файл [create_curated_cases.py](file:///Users/johnwunderbellen/Timezone_bot/tests/langsmith/create_curated_cases.py) и добавь в список `EXAMPLES`:

```python
{
    "description": "[TOOL=publish] Мой новый кейс",
    "inputs": {
        "text": "встреча в 15:30",
        "history": "(no prior messages)",
        "sender_id": "u1",
        "sender_name": "Иван",
        "timestamp": "2026-03-20T10:00:00Z",
    },
    "outputs": {
        "event": True,
        "tool": "publish_event",   # ← publish / update_previous_event / null
        "time": "15:30",           # ← ожидаемое время, или null
    },
},
```

Потом снова:
```bash
uv run python tests/langsmith/create_curated_cases.py   # загрузить
uv run python tests/langsmith/run_eval.py               # проверить
```

> **Какой `tool` ставить?**
> - `"publish_event"` — первое упоминание события в чате
> - `"update_previous_event"` — в history есть строка `[BOT]: detected: ...`
> - `null` — событие не обнаружено

---

## Сравнить два эксперимента (до/после изменения промпта)

```bash
# До изменений
uv run python tests/langsmith/run_eval.py --prefix agent-v1

# Поменял промпт → запускаешь снова
uv run python tests/langsmith/run_eval.py --prefix agent-v2
```

В UI → вкладка **Experiments** → выбери оба → **Compare** — видишь diff построчно.
