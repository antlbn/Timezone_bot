# 02. Capture Logic Specification

This specification describes the logic for detecting time patterns in user messages.
We intentionally keep the mental модель простой:
- есть строки, **похожие на время** (regex ловит всё, что выглядит как время),
- есть **ключевые слова** (про встречи / звонки / завтра и т.п.),
- если есть что‑то из этого — зовём LLM, и только **после решения LLM** запускаем конвертацию времени.

High-level dataflow (один слой детекции):

```
Message
  │
  ├─▶ [Time-like Regex Patterns] ──▶ time_candidates (e.g. ["19:00", "5 pm", "8"])
  ├─▶ [Keywords (RU/EN)]            ──▶ context_hints
  │
  └─▶ Prefilter (regex OR keywords) ──▶ LLM Event Detector ──▶ trigger?
                                               │
                                ┌──────────────┴──────────────┐
                                │                             │
                            trigger = true                trigger = false
                                │                             │
                                ▼                             ▼
                     Transform Module (uses          Do nothing (no reply)
                     time_candidates that parse)
```

## 1. Concept
The agent must scan incoming messages for **time-like tokens** and keywords:

- **Regex** даёт нам список `time_candidates` (строки, похожие на время).
- **Keywords** (из `event_detection.prefilter`) дают нам контекст “про встречи / звонки”.

Дальше:
- Если нет ни кандидатов, ни keywords → ничего не делаем.
- Если есть кандидаты или keywords → вызываем LLM (см. `13_event_detection.md`).
- Если LLM вернула `trigger=false` или низкую уверенность → тихо выходим.
- Если LLM вернула `trigger=true` → пробуем **сконвертировать только те `time_candidates`, которые реально парсятся во время** (через `parse_time_string` в `transform.py`).


## 2. Time-like Patterns (Regex)

1.  **24h format**: `HH:MM`
    * Examples: `19:00`, `09:30`, `14:15`
2.  **12h format**: `H:MM AM/PM` or `H AM/PM` or `HH AM/PM`
    * Examples: `5 PM`, `05:00 pm`, `10 am`, `9:30 PM` (case insensitive)
3.  **Bare hours (candidates)**: integers `0–23` that могут быть временем:
    * Examples: `"8"`, `"19"` in phrases like `«в 8 норм?»`

> **Note:** Exact patterns are defined in `configuration.yaml`:
> - `capture.patterns` — паттерны для строк, которые мы точно считаем “временем” (используются и в regex‑слое, и в `extract_times`).
> - `event_detection.numeric_candidate_pattern` — паттерн для “голых чисел” (используется только как дополнительный сигнал для LLM).

## 3. Handling Multiple Values
If a message contains multiple timestamps, the bot must extract all of them.

**Scenario:**
> "Let's call at 18:00 or maybe 19:30?"

**Parsing Result:**
`["18:00", "19:30"]`

The bot must attempt to convert each of these time-like strings **only if** LLM returned `trigger=true`. Values that cannot be parsed into a valid time are silently ignored at conversion stage.

## 4. Match Examples (Test Cases)

| User Message | Expected Result (list) | Comment |
| :--- | :--- | :--- |
| `Meeting at 15:00` | `["15:00"]` | Clean 24h match |
| `let's go at 19:00` | `["19:00"]` | Ignore preposition, take time |
| `Call me at 5 pm` | `["5 pm"]` | 12h format |
| `10:30 am or 11:30 am` | `["10:30 am", "11:30 am"]` | Multiple times |
| `Call at 14:00 MSK` | `["14:00"]` | "MSK" is parsed separately or ignored at this stage (MVP: take 14:00 as user's local time) |
| `Price 500` | `[]` | Not a time |
| `Score 12:45` | `["12:45"]` | **Edge Case**: looks like a match score. Regex will match, but LLM is expected to classify it as `trigger=false`. |

---

## 5. Implementation Instructions

1. Use Python's `re` module.
2. Regex‑паттерны читаются из `configuration.yaml`:
   - `capture.patterns` — основные шаблоны времени (24h / 12h).
   - `event_detection.numeric_candidate_pattern` — дополнительный шаблон для “голых чисел”.
3. Для LLM‑детектора следует использовать **объединение** всех паттернов, чтобы сформировать список `time_candidates`.
4. Функция `extract_times(text: str) -> List[str>` может продолжать использовать только `capture.patterns` (строгие времена), так как на этапе трансформации всё равно применяется `parse_time_string`, который отфильтрует неподходящие значения.

