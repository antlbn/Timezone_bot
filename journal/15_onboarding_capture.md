# 15. Onboarding Message Capture

## 1. Purpose

This document defines how the bot preserves a time-event message while the author is completing lazy onboarding.

## 2. Why It Exists

Without capture, the bot would either:

- lose the original coordination message,
- force the user to repeat it after setup,
- or reply too late without context.

The pending-message mechanism avoids all three.

## 3. Memory Layers

### `users_snapshot`

- in-memory user cache,
- reduces repeated SQLite reads,
- invalidated when user profile state changes.

### `onboarding_frozen`

- in-memory store for frozen messages waiting on onboarding outcome,
- keyed so the message can later be released back into its original chat flow,
- expires by `onboarding_timeout_seconds`.

## 4. Frozen Message Lifecycle

1. LLM detects a time coordination event.
2. Sender is found to have no stored timezone.
3. The message is frozen instead of processed immediately.
4. Onboarding starts asynchronously.
5. The frozen message is later either released or discarded.

## 5. Release Rules

| Outcome | Result |
|---|---|
| Onboarding success | Release and process normally |
| Onboarding decline with valid `tz_city` | Release and process using the explicit source location |
| Onboarding decline without `tz_city` | Discard |
| Onboarding timeout / ignore | Discard |

## 6. UX Rule

When a frozen message is released, the bot should reply to the original message where platform capabilities allow it, preserving visual context.

## 7. Non-Goals

- durable persistence of frozen messages across process restarts,
- indefinite retention of pending messages,
- bypassing onboarding rules for users without a stored timezone.
