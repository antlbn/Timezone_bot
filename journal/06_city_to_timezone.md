# Technical Spec: City → Timezone Mapping

## 1. Overview

Module for determining IANA timezone by city name.
Uses geocoding (Nominatim/OSM) + TimezoneFinder.

---

## 2. Technology Stack

| Library | Purpose |
|---------|---------|
| `geopy` | Geocoding (OpenStreetMap Nominatim) |
| `timezonefinder` | Coordinates → IANA timezone |

### Country Flags

Nominatim returns `country_code` (DE, US, JP). Mapping to emoji:

```python
def get_country_flag(country_code: str) -> str:
    return "".join(chr(ord(c) + 127397) for c in country_code.upper())
# "DE" → 🇩🇪, "US" → 🇺🇸, "JP" → 🇯🇵
```

---

## 3. Workflow


```
User enters city
       │
       ▼
   Geocoding
       │
   ┌───┴───┐
   ▼   ▼   ▼
   0   1   >1  results
   │   │    │
   ▼   ▼    ▼
Fallback Save Inline buttons
```

### Logic:

1. **0 results** → Fallback (ask for system time)
2. **1+ results** → MVP: Take the first (Best Match), save timezone, confirm to user. (Disambiguation — Future Scope).

---

## 4. Disambiguation (Inline Buttons)

If multiple cities with the same name are found:

```
🌍 Found multiple options for "Paris":

[Paris, France 🇫🇷]  [Paris, Texas, USA 🇺🇸]
```


- User clicks button → save selected timezone
- Callback data format: `tz:Europe/Moscow`

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

Nominatim requires:
- Max 1 request/second
- Mandatory User-Agent

Use `RateLimiter` from geopy.

---

## 7. Edge Cases

| Case | Handling |
|------|----------|
| Typo in name | Nominatim often finds fuzzy match |
| City in different languages | Nominatim is multilingual |
| Empty input | Repeat the question |
| Fallback time '14:00' matched as toponym | fallback -> check REGEX first, then geocoding |
---

## 8. Out of Scope (MVP)

- **Inline buttons disambiguation** — when >1 result, take the first
- **RateLimiter** — Nominatim timeout=5s is sufficient for MVP
- **`get_multiple_locations()`** — function exists but not used

---

## 9. Future Improvements

- [ ] Direct IANA timezone recognition (`Europe/Berlin`) — for advanced users
- [ ] Inline buttons for selecting from multiple cities (though writing "Paris, TEXAS" already works correctly)
