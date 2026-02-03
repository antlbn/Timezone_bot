# Handover: Architecture & Design Decisions

This document summarizes the technical "brain" of the project for future maintainers.

##  Core Architecture: UTC-Pivot
To avoid messy N-to-N timezone conversions, we use a **UTC-Pivot** strategy:
1.  Captured time (e.g., "5 pm") is parsed into a `time` object.
2.  It is combined with the sender's timezone to create a UTC-aware datetime.
3.  This UTC "pivot" is then converted to all active chat members' timezones.

##  Key Components

- **Middleware (`src/commands/middleware.py`)**: 
  `PassiveCollectionMiddleware` monitors messages. Known participants (who set their timezone) are automatically added to the chat's active list.
- **Capture Logic (`src/capture.py`)**: 
  regex-based extraction via `configuration.yaml`.
- **Geocoding (`src/geo.py`)**: 
  Uses Nominatim (OSM) and TimezoneFinder.
- **Database (`src/storage/`)**: 
  SQLite (`aiosqlite` wrapper over standard `sqlite3`). Tables: `users`, `chat_members`.

##  Design Decisions

| Choice | Reasoning | Trade-off |
| :--- | :--- | :--- |
| **SQLite** | Zero config (Python std lib), fast enough for MVP. | Not for large clusters. |
| **MemoryStorage** | Simple FSM. | States lost on reboot. |

##  Design Patterns
- **Singleton**: Used for `config`, `logger`, and `storage` (via `src/storage/__init__.py`). Ensures single point of truth and efficient connection reuse.

## Known Limitations

### Cooldown Tracking
The bot tracks reply cooldown in-memory (`_last_reply` dict in `src/commands/common.py`):
- Prevents spam in a single session
-  **Does NOT persist** between bot restarts
-  Not suitable for multi-instance deployments

**Future improvement:** Move to Redis or database.

### Database Caching
Currently, the bot performs direct SQLite reads for every message to check member existence.
-  Simple and consistent (ACID)
-  Disk I/O heavy on high load

**Future improvement:** Implement `In-Memory Caching (CachedDb)` to preload data.

##  Future Roadmap
1.  **Multi-Platform**: Support Discord/WhatsApp.
2.  **Inline Buttons**: Better disambiguation for cities.
3.  **Fuzzy Detection**: Use `rapidfuzz` for typo tolerance.
4.  **Error Handling**: Global middleware to catch unhandled exceptions and notify admins (e.g. Sentry).
5.  **In-Memory Caching (CachedDb)**: Implement a Write-Through cache (preload all users/chats at startup) to minimize DB disk I/O.

##  Testing
- **Zero Config**: Tests use temporary sqlite databases. No setup required.


