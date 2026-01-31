# Handover: Architecture & Design Decisions

This document summarizes the technical "brain" of the project for future maintainers.

##  Core Architecture: UTC-Pivot
To avoid messy N-to-N timezone conversions, we use a **UTC-Pivot** strategy:
1.  Captured time (e.g., "5 pm") is parsed into a `time` object.
2.  It is combined with the sender's timezone to create a UTC-aware datetime.
3.  This UTC "pivot" is then converted to all active chat members' timezones.

##  Key Components

- **Middleware (`src/commands.py`)**: 
  `PassiveCollectionMiddleware` monitors messages. Known participants (who set their timezone) are automatically added to the chat's active list.
- **Capture Logic (`src/capture.py`)**: 
  regex-based extraction via `configuration.yaml`.
- **Geocoding (`src/geo.py`)**: 
  Uses Nominatim (OSM) and TimezoneFinder.
- **Database (`src/storage.py`)**: 
  SQLite (`aiosqlite`). Tables: `users`, `chat_members`.

##  Design Decisions

| Choice | Reasoning | Trade-off |
| :--- | :--- | :--- |
| **SQLite** | Zero config, fast enough for MVP. | Not for large clusters. |
| **MemoryStorage** | Simple FSM. | States lost on reboot. |

##  Future Roadmap
1.  **Multi-Platform**: Support Discord/WhatsApp.
2.  **Inline Buttons**: Better disambiguation for cities.
3.  **Fuzzy Detection**: Use `rapidfuzz` for typo tolerance.
4.  **Error Handling**: Global middleware to catch unhandled exceptions and notify admins (e.g. Sentry).

