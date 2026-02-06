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
  level: INFO   # DEBUG — for development, INFO — for production
```

---

## 3. Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Raw Telegram updates (JSON) |
| `INFO` | Main events: "Bot started", "Converted time for user X" |
| `WARNING` | Non-standard situations (API timeout, DB lock), operation continues |
| `ERROR` | Critical errors (Traceback) |

---

## 4. Simple Context
In log messages, simply add chat ID if available:
`[chat:123] Timezone set to Europe/Berlin`

---

## 5. Exception Handling
We do **not hide** errors.
- **Failures**: All exceptions in `except` blocks (Geo API, DB) must be logged as `WARNING` or `ERROR`.
- **Silent Failures**: `except: pass` is **prohibited** for critical logic.
