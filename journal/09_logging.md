# 09. Logging

This document defines the runtime logging contract.

## 1. Goals

Logging should make it possible to:

- diagnose platform failures,
- understand onboarding behavior,
- inspect event-processing decisions,
- detect bottlenecks and slow external dependencies.

## 2. Base Strategy

Current implementation uses Python `logging` to `stdout`.

That is sufficient for local runs, Docker logs, and simple production deployments.

## 3. Levels

| Level | Use |
|---|---|
| `DEBUG` | detailed control flow, prompt/context diagnostics, cache details |
| `INFO` | normal lifecycle events and successful high-level actions |
| `WARNING` | degraded behavior with recovery, such as edit failures or API timeouts |
| `ERROR` | failed operations that prevented expected behavior |

## 4. Required Context

Log lines should include enough context to correlate behavior:

- platform when relevant,
- chat or guild id,
- user id when helpful,
- operation name or phase.

The event-processing pipeline already uses contextual logging adapters inside the orchestration path.

## 5. External Dependency Logging

Calls that touch external systems must log failures explicitly:

- LLM provider
- geocoding provider
- platform API edits/deletes/sends
- SQLite operational errors

Silent failure for core logic is not acceptable.

## 6. Performance-Relevant Logging

Because the bot is async and can bottleneck on slow dependencies, logging should make latency issues diagnosable.

Recommended signals:

- slow geocoding calls,
- repeated geocoding failures,
- dropped stale messages,
- lock/backlog pressure per chat,
- LLM invocation failures and retries.

Current runtime already emits warnings for slow geo-resolution calls and for Telegram membership verification failures during reply preparation.

## 7. Rebuild Notes

If logging is rebuilt:

1. keep stdout as the default sink,
2. keep structured context in message text or adapters,
3. preserve explicit logging around external dependency failures,
4. add timing metrics before adding heavy observability infrastructure.
