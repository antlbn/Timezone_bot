# Technical Spec: Testing Strategy

## 1. Philosophy (MVP)
We follow a **Pragmatic approach**:
1.  **Logic First**: Automatically test only complex business logic (Regex, time math).
2.  **Manual UI**: Test Telegram interactions (buttons, commands) manually.
3.  **Zero External Deps**: Use standard library `unittest` (or simple `pytest` without complex plugins).

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

These tests should run before every commit.

### Scope:
1.  **Capture Patterns**:
    -   Check all examples from `configuration.yaml`
    -   Edge cases (no time, garbage, "price 500")
2.  **Transformation Logic**:
    -   UTC → Target TZ conversion
    -   Day change handling (Day +1 / -1)
    -   Response string formatting
3.  **Resilience (L2)**:
    -   API error handling (Geo timeout)
    -   Database stability (Middleware catch)
    -   Garbage data parsing
4.  **Handlers (L1.5)**:
    -   Unit tests for commands (`cmd_me`, `cmd_settz`)
    -   Mocking `aiogram.types.Message` and `storage`
    -   Verify `message.answer` is called with expected text

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

For integration and UI verification, use a checklist (`task.md` Phase 4).

**Key scenarios:**
1.  **Startup**: Bot starts, DB is created.
2.  **New User Flow**: `/tb_settz` → enter city → save.
3.  **Group Chat**:
    -   User A (Berlin) writes "15:00"
    -   User B (NY) sees "09:00 New York"
4.  **Error Handling**: Enter non-existent city (fallback should work).

---

## 5. Continuous Integration (Future)
In the future (Post-MVP) add GitHub Actions:
- Linting (`ruff`)
- Running tests (`python -m unittest discover tests`)

---

## 6. Database in Tests
**Important:** Running tests does **not require** the `data/bot.db` file.
- **L1.5 (Handlers)**: Use `unittest.mock` (don't touch disk at all).
- **L2 (Integration)**: Tests in `test_storage.py` automatically create and delete a **temporary DB file** (`tests/test_bot.db`).
This guarantees that tests can run on a clean machine right after `git clone`.
