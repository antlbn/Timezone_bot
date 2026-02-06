# Handover: Architecture & Design Decisions

This document summarizes the technical "brain" of the project for future maintainers.

---

##  Core Architecture: UTC-Pivot

To avoid messy N-to-N timezone conversions, we use a **UTC-Pivot** strategy:
1.  Captured time (e.g., "5 pm") is parsed into a `time` object.
2.  It is combined with the sender's timezone to create a UTC-aware datetime.
3.  This UTC "pivot" is then converted to all active chat members' timezones.

---

## Platform Architecture

The bot supports **Telegram** and **Discord** via separate adapters sharing a common core:

```
┌─────────────┐     ┌─────────────┐
│  Telegram   │     │  Discord    │
│  (aiogram)  │     │(discord.py) │
└──────┬──────┘     └──────┬──────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│src/commands/│     │src/discord/ │
│  + FSM      │     │  + UI       │
│  + Middleware     │  (buttons)  │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 ▼
┌───────────────────────────────────────┐
│           SHARED CORE                 │
│  capture | transform | formatter     │
│  storage | geo | config | logger     │
└───────────────────────────────────────┘
```

### Platform-Specific Components

| Component | Telegram | Discord |
|-----------|----------|---------|
| **User Interaction** | Text replies + ForceReply (FSM) | Buttons + Modals (UI Views) |
| **State Management** | `MemoryStorage` (aiogram FSM) | Stateless (modals handle it) |
| **Middleware** | `PassiveCollectionMiddleware` | N/A (uses events) |
| **Stale User Handling** | Manual `/tb_remove` command | Auto-cleanup on time mention |
| **Member Tracking** | Bot doesn't know when user leaves | `on_member_remove` event |

---

##  Key Components

### Shared (Core)

- **Capture Logic (`src/capture.py`)**: Regex-based time extraction via `configuration.yaml`.
- **Geocoding (`src/geo.py`)**: Uses Nominatim (OSM) and TimezoneFinder.
- **Storage (`src/storage/`)**: SQLite via `aiosqlite`. Tables: `users`, `chat_members`. Supports `platform` column for multi-platform.
- **Formatter (`src/formatter.py`)**: Generates conversion reply text.

### Telegram-Specific

- **Middleware (`src/commands/middleware.py`)**: `PassiveCollectionMiddleware` monitors messages and auto-adds known participants to chat list.
- **FSM States (`src/states.py`)**: `SetTimezone`, `RemoveMember` states for multi-step flows.
- **MemoryStorage**: Simple in-memory FSM storage. States lost on reboot.

### Discord-Specific

- **UI Components (`src/discord/commands.py`)**: `SetTimezoneView`, `FallbackView`, modals for interactive input.
- **Events (`src/discord/events.py`)**: `on_message` (with auto-cleanup), `on_member_remove`.
- **Button Security**: Buttons are restricted to target user only.

---

##  Design Decisions

| Choice | Reasoning | Trade-off |
| :--- | :--- | :--- |
| **SQLite** | Zero config (Python std lib), fast for MVP | Not for large clusters |
| **MemoryStorage (Telegram)** | Simple FSM for dialog flows | States lost on reboot |
| **Stateless Modals (Discord)** | No FSM needed, modals handle input | Cannot do multi-step dialogs |
| **Separate Adapters** | Platform-specific UX, shared core | Some code duplication in handlers |

##  Design Patterns

- **Singleton**: Used for `config`, `logger`, and `storage`. Ensures single point of truth.
- **Adapter Pattern**: Telegram (`src/commands/`) and Discord (`src/discord/`) are thin adapters over shared core.

---

## Known Limitations

### Cooldown Tracking
The bot tracks reply cooldown in-memory (`_last_reply` dict in `src/commands/common.py`):
- Prevents spam in a single session
- **Does NOT persist** between bot restarts
- Not suitable for multi-instance deployments

**Future:** Move to Redis or database.

### Database Caching
Currently, direct SQLite reads for every message. Simple but disk I/O heavy on high load. Architecture is ready for caching (see `05_storage.md`).

---

##  Future Roadmap

1.  **Error Handling**: Global middleware to catch exceptions (e.g. Sentry).
2.  **In-Memory Caching**: Write-Through cache to minimize DB I/O.
3.  **WhatsApp Support**: New adapter following same pattern.

---

##  Testing

- **Zero Config**: Tests use temporary sqlite databases. No setup required.
