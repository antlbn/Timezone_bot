# Technical Spec: Logging

## 1. Overview (MVP)
Minimalistic strategy:
- **Output**: Standard output (`stdout`) — ideal for Docker.
- **Library**: Built-in Python `logging`.
- **No external services** (Sentry, etc. — out of scope).

---

## 2. Configuration

`configuration.yaml`:
```yaml
logging:
  level: INFO   # DEBUG | INFO | WARNING | ERROR | CRITICAL
```

---

## 3. Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Development-level diagnostics: prompt/debug context, detailed runtime flow, low-level troubleshooting |
| `INFO` | Main events: "Bot started", "Converted time for user X" |
| `WARNING` | Non-standard situations (API timeout, DB lock), operation continues |
| `ERROR` | Operation failed for a concrete action or request; traceback/log context should be preserved |
| `CRITICAL` | Process-level or unrecoverable failure requiring immediate operator attention |

---

## 4. Simple Context
In log messages, simply add chat ID if available:
`[chat:123] Timezone set to Europe/Berlin`

Starting from **2026-03-16**, the LLM pipeline uses `logging.LoggerAdapter` to automatically inject `[platform:chat_id]` into all logs within the pipeline context.

---

## 5. Exception Handling
We do **not hide** errors.
- **Failures**: All exceptions in `except` blocks (Geo API, DB) must be logged as `WARNING` or `ERROR`.
- **Silent Failures**: `except: pass` is **prohibited** for critical logic.

## 6. Required Operational Logs

- State-changing handlers must emit an observable log entry after the state change succeeds.
- Logs required by the MVP include at least member removal, timezone save/update, onboarding decline, and LLM attempt failure.
- Required logs must be reachable in the executed control flow; logging placed after a terminal `return` does not satisfy the contract.
