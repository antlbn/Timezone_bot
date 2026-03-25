# 10. Testing Strategy

This document defines the quality strategy for the current system.

## 1. Goal

The test suite must protect the parts of the bot that are easy to break and expensive to debug:

- event detection contract,
- onboarding behavior,
- storage invariants,
- platform adapter handlers,
- publish/update semantics.

## 2. Test Layers

| Layer | Scope | Purpose |
|---|---|---|
| Unit | pure logic modules | Validate parsing, transformation, formatting, and local decisions. |
| Handler tests | Telegram / Discord command and event handlers | Verify adapter behavior, branching, and side effects with mocks. |
| Storage tests | SQLite-backed data access | Verify schema and persistence contracts. |
| Integration-focused runtime tests | event processing and onboarding flows | Verify multi-module behavior without real network calls. |
| Manual verification | real Telegram / Discord UX | Check platform-specific interaction details that mocks cannot fully capture. |

## 3. Automated Coverage Priorities

Highest priority:

1. detection-only onboarding behavior for unregistered users,
2. no fake publish traces in real chat thread memory,
3. no replay of pre-onboarding messages,
4. correct persistence of `onboarding_declined`,
5. `publish_event` vs `update_previous_event` behavior,
6. member cleanup and membership reads,
7. city/timezone resolution fallbacks,
8. stale-message dropping under age guards.

## 4. Test Inventory

Current suite is organized roughly like this:

| File | Focus |
|---|---|
| `tests/test_event_detection.py` | detection pipeline, structured outputs, publish/update behavior |
| `tests/test_lazy_onboarding.py` | Telegram onboarding trigger behavior |
| `tests/test_soft_onboarding_new.py` | Telegram DM onboarding, decline, cooldown, settings flow |
| `tests/test_handlers.py` | Telegram commands and handler behavior |
| `tests/test_discord_on_message.py` | Discord message-path onboarding and detection behavior |
| `tests/test_discord_handlers.py` | Discord commands and UI integration points |
| `tests/test_discord_events.py` | Discord member removal and scheduled cleanup |
| `tests/test_discord_extended.py` | broader Discord UX and edge behaviors |
| `tests/test_storage_pending.py` | invite cooldown state only |

## 5. Manual Verification

Manual checks are still required for:

- Telegram deep links,
- message auto-cleanup timing,
- Discord button/modal UX,
- embed rendering,
- permission and visibility behavior on real platforms.

Minimum manual scenarios:

1. new Telegram user triggers onboarding invite from group,
2. Telegram DM setup succeeds and bot starts from the next message,
3. Telegram decline suppresses future automatic invites,
4. new Discord user receives button-based onboarding,
5. Discord modal success stores timezone and confirms future-message behavior,
6. follow-up event edits or republishes correctly in a busy chat.

## 6. Test Philosophy

1. Prefer deterministic tests over brittle end-to-end automation.
2. Mock platform APIs aggressively.
3. Keep real external services out of CI.
4. Treat docs and tests as enforcement of product invariants, not just implementation detail.

## 7. Rebuild Notes

If the system is rebuilt, restore the tests around onboarding and memory boundaries early. They protect the architecture, not just the UI.
