# 📄 Technical Spec: Time Transformation Module (TTM)

## 1. Overview
Module designed for converting time between arbitrary timezones with protection from "political" time shifts (legislative changes) and DST transitions (daylight saving time).

> **v1.2 Update**: The transformation module now accepts an optional `source_tz` parameter. When the LLM Event Detector returns a non-null `event_location`, the application geocodes it and passes the resulting IANA timezone as `source_tz`, overriding the sender's DB timezone for this conversion only.

## 2. Technology Stack
* **Core Libraries:** 
    * `zoneinfo`: Native IANA database support (PEP 615 standard).
    * `tzdata`: Primary source of up-to-date timezone data.

## 3. Core Architecture: "UTC-Pivot"
Any time transformation must go through a "zero point" (UTC). Direct conversion between local zones ("Zone A -> Zone B") is prohibited to minimize errors.

```
    Source Time         UTC              Target Zones
    (sender DB TZ                            
     OR event_location)                 
        │                │                    
   "12:00"               │                    
   New York 🇺🇸           │                    
   (event_location)      │                    
        └───────▶ 17:00 UTC ───────┬─▶ 19:00 Berlin 🇩🇪
                         │         │
                         │         ├─▶ 12:00 New York 🇺🇸
                         │         │
                         │         └─▶ 02:00⁺¹ Tokyo 🇯🇵
```

**Source TZ resolution:**
- If `event_location` != null → `source_tz = geocode(event_location).iana_tz`
- If `event_location` == null → `source_tz = sender's DB timezone`

### Workflow:
1. **Extraction**: `times[]` received from LLM Event Detector (`14_llm_module.md`). Optional `source_tz` override also provided if `event_location` was geocoded.
2. **Anchoring**: Binding to current date (`datetime.now()`) to determine the current DST mode.
3. **Localization**: Creating an `Aware datetime` object in the **source timezone** (`source_tz` if provided, else sender's DB TZ).
4. **Normalization**: Shifting the object to **UTC** (reference point).
5. **Projection**: Shifting from UTC to the list of target zones (`target_timezone_names`). **Includes the sender's own zone** so they see their local equivalent too.


## 4. Maintenance & Data Integrity
To ensure data relevance (protection from sudden timezone changes by governments):

* **Update Strategy**:
  * **Manual Maintenance**: Updating the `tzdata` package via `uv lock --upgrade` when new IANA database versions are released.
  * (Future) Auto-update task - deferred.
* **Command**: `uv sync --upgrade`
* **Storage Policy**: Only **IANA names** (e.g. `Europe/Moscow`) are allowed in the database (SQLite). Storing numeric offsets (e.g. `+3`) is strictly prohibited.

