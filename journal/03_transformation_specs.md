# 📄 Technical Spec: Time Transformation Module (TTM)

## 1. Overview
Module designed for converting time between arbitrary timezones with protection from "political" time shifts (legislative changes) and DST transitions (daylight saving time).

## 2. Technology Stack
* **Core Libraries:** 
    * `zoneinfo`: Native IANA database support (PEP 615 standard).
    * `tzdata`: Primary source of up-to-date timezone data.

## 3. Core Architecture: "UTC-Pivot"
Any time transformation must go through a "zero point" (UTC). Direct conversion between local zones ("Zone A -> Zone B") is prohibited to minimize errors.

```
    Local Time          UTC              Target Zones
    (sender)                            
        │                │                    
   "14:00"               │                    
   Berlin 🇩🇪             │                    
        │                │                    
        └───────▶ 13:00 UTC ───────┬─▶ 08:00 New York 🇺🇸
                         │         │
                         │         ├─▶ 22:00 Tokyo 🇯🇵
                         │         │
                         │         └─▶ 13:00 London 🇬🇧
```

### Workflow:
1. **Extraction**: Received from capture_module
2. **Anchoring**: Binding to current date (`datetime.now()`) to determine the current DST mode.
3. **Localization**: Creating an `Aware datetime` object in the sender's zone.
4. **Normalization**: Shifting the object to **UTC** (reference point).
5. **Projection**: Shifting from UTC to the list of target zones (`target_timezone_names`).


## 4. Maintenance & Data Integrity
To ensure data relevance (protection from sudden timezone changes by governments):

* **Update Strategy**:
  * **Manual Maintenance**: Updating the `tzdata` package via `uv lock --upgrade` when new IANA database versions are released.
  * (Future) Auto-update task - deferred.
* **Command**: `uv sync --upgrade`
* **Storage Policy**: Only **IANA names** (e.g. `Europe/Moscow`) are allowed in the database (SQLite). Storing numeric offsets (e.g. `+3`) is strictly prohibited.

