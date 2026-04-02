# Technical Spec: Testing Strategy

## 1. Philosophy (MVP)
We follow a pragmatic approach:
1. logic first,
2. manual UI verification,
3. plain `pytest` with mocks.

## 2. Test Pyramid

| Layer | Type | Scope | Automation | Tool |
|-------|------|-------|------------|------|
| **L1** | **Unit** | `src/event_detection/`, `src/transform.py`, `src/geo.py`, `src/formatter.py` | ✅ Automated | `pytest` |
| **L1.5** | **Handlers** | Telegram and Discord command/event handlers | ✅ Automated | `pytest` + mocks |
| **L2** | **Integration** | storage, onboarding/runtime flow, reply building | ✅ Automated | `pytest` |
| **L3** | **E2E / UI** | bot commands, dialogs, flows | ❌ Manual | Telegram App, Discord |

## 3. Automated Logic Tests

These tests should run before every commit.

### Scope
1. **Event Detection runtime**
   - parse `time_mentioned`, `tz_city`, `event_title`, `am_pm_clear`
   - malformed JSON must fail safe to silence
   - invalid points (`99:99`, wrong types, missing required fields) must be dropped
   - if all points are invalid, runtime must stay silent
2. **Transformation / formatting**
   - UTC → target TZ conversion
   - `tz_city` source override
   - day shifts
   - ambiguous-point presentation with `AM/PM?`
3. **Resilience**
   - LLM fallback behavior
   - API errors
   - garbage data parsing
4. **Handlers**
   - onboarding triggers only when `time_mentioned=true`
   - no publish when no usable points survive validation

### Primary files
- `tests/test_event_detection.py`
- `tests/test_integration.py`
- `tests/test_formatter.py`
- `tests/test_transform.py`
- `tests/test_geo.py`
- `tests/test_storage.py`
- `tests/test_handlers.py`
- `tests/test_discord_*.py`

## 4. Manual Verification

Key scenarios:
1. configured sender + clear point -> normal conversion
2. configured sender + ambiguous point -> `AM/PM?`
3. unknown sender + `time_mentioned=true` -> onboarding
4. malformed provider response -> silence, no crash

## 5. Continuous Integration (Future)

Future CI should run:
- linting
- full `pytest`

## 6. Database in Tests

Running tests must not require the production DB.
- handler tests use mocks
- storage tests use a temporary DB

## 7. Runtime Reset and Isolation

- Runtime caches that affect deterministic behavior must expose reset hooks.
- Tests may patch env vars, config getters, and YAML-backed config values in a single pytest process.
- Stale config state leaking between tests is a bug.
