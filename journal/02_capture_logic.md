# 02. Capture Logic Specification

## 1. Concept: Optional Prefilter

This module (`src/capture.py`) implements an **optional prefilter** for the LLM Event Detector (`14_llm_module.md`). 

The logic is simple:
- Some chats have high message volume, and querying the LLM for every message might be costly.
- If the prefilter is **enabled** in `configuration.yaml`, the bot will only call the LLM if a message contains strings that **look like time** (regex) or **keywords** related to meetings/calls.
- If the prefilter is **disabled** (the default), this module is skipped, and the LLM receives every message directly.

**Important Note**: This module does **not** extract the final times used for the bot's response. It only decides "should we call the LLM?" The LLM itself remains responsible for extracting the actual `points[]` (time and location).

**Deferred Processing**: Since 2026-03-15, if the capture logic identifies a time but the user is not registered, the message is **deferred** (saved to Redis) and processed after onboarding. See `15_onboarding_capture.md`.

Message
  │
  ├─▶ [Time-like Regex]      ──▶ time_candidates found?
  ├─▶ [Numeric Regex]        ──▶ plain hours found?
  ├─▶ [Keywords (RU/EN)]     ──▶ keywords found?
  │
  └─▶ Decision: 
        If (time_candidates) OR (plain hours AND keywords)
            ──▶ Call Event Detector (LLM)
        Else
            ──▶ Ignore message (save LLM cost)
```

## 2. Prefilter Configuration

Controlled via `configuration.yaml`:
```yaml
event_detection:
  prefilter:
    enabled: false  # Default is false (LLM gets everything)
    require_time_regex_or_keywords: true
```

## 3. Time-like Patterns (Regex)

These patterns are used to detect potential time mentions.

1. **24h format**: `HH:MM` — e.g. `19:00`, `09:30`
2. **12h format**: `H:MM AM/PM` — e.g. `5 PM`, `9:30 PM`
3. **Bare hours (candidates)**: integers `0–23` — e.g. `"8"`, `"19"` (requires accompanying keyword if `require_time_regex_or_keywords` is true).

Patterns are defined in `configuration.yaml` under `capture.patterns` and `event_detection.prefilter.numeric_candidate_pattern`.
