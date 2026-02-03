# Technical Spec: City → Timezone Mapping

## 1. Overview

Модуль для определения IANA timezone по названию города.
Использует геокодинг (Nominatim/OSM) + TimezoneFinder.

---

## 2. Technology Stack

| Library | Purpose |
|---------|---------|
| `geopy` | Geocoding (OpenStreetMap Nominatim) |
| `timezonefinder` | Координаты → IANA timezone |

### Country Flags

Nominatim возвращает `country_code` (DE, US, JP). Маппинг в emoji:

```python
def get_country_flag(country_code: str) -> str:
    return "".join(chr(ord(c) + 127397) for c in country_code.upper())
# "DE" → 🇩🇪, "US" → 🇺🇸, "JP" → 🇯🇵
```

---

## 3. Workflow


```
Юзер вводит город
       │
       ▼
   Geocoding
       │
   ┌───┴───┐
   ▼   ▼   ▼
   0   1   >1  результатов
   │   │    │
   ▼   ▼    ▼
Fallback Save Inline buttons
```

### Логика:

1. **0 результатов** → Fallback (спросить системное время)
2. **1+ результат** → MVP: Берем первый (Best Match), сохраняем timezone, подтверждаем юзеру. (Disambiguation — Future Scope).

---

## 4. Disambiguation (Inline Buttons)

Если найдено несколько городов с одинаковым названием:

```
🌍 Нашёл несколько вариантов для "Paris":

[Paris, France 🇫🇷]  [Paris, Texas, USA 🇺🇸]
```


- Юзер нажимает кнопку → сохраняем выбранный timezone
- Callback data формат: `tz:Europe/Moscow`

---

## 5. Fallback: System Time

If city is not found:

1. Bot asks: `"City not found. Reply with your current time (e.g. 14:30) or try another city name:"`
2. User can reply with:
   - **Time** (e.g. "14:30") → Calculate UTC offset, save as "UTC+X 🌐"
   - **City** (retry) → Attempt geocoding again
3. If neither recognized → repeat prompt

---

## 6. Rate Limiting

Nominatim требует:
- Max 1 request/second
- Обязательный User-Agent

Использовать `RateLimiter` из geopy.

---

## 7. Edge Cases

| Case | Handling |
|------|----------|
| Typo в названии | Nominatim часто находит fuzzy match |
| Город на разных языках | Nominatim multilingual |
| Пустой ввод | Повторить вопрос |

---

## 8. Out of Scope (MVP)

- **Inline buttons disambiguation** — при >1 результате берём первый
- **RateLimiter** — Nominatim timeout=5s достаточен для MVP
- **`get_multiple_locations()`** — функция есть, но не используется

---

## 9. Future Improvements

- [ ] Распознавание IANA timezone напрямую (`Europe/Berlin`) — для продвинутых юзеров
- [ ] Inline buttons для выбора из нескольких городов
