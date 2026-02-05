# Timezone Bot

Passive timezone synchronization utility for distributed teams.

---

## Goal

Eliminate manual timezone conversion in group chats. The bot monitors conversations, detects time mentions, and broadcasts equivalent times for all participants.

---

## How It Works

```
"Meet at 5pm"  ───>  Bot captures time  ───>  Reply with times for all members
                                              
                                              14:00 Berlin | 08:00 New York | 22:00 Tokyo
```

When someone mentions a time in the chat, the bot automatically:
- Detects the time pattern in the message
- Looks up timezones of all registered chat members
- Converts and broadcasts the time for everyone

---

## Design Principles

**Zero-friction approach:**
- No commands needed for conversion — it happens automatically
- Plug-and-play — adding bot to group is the only setup
- Self-registration — user registers timezone once, remembered across all groups
- Minimal interference — bot responds only when time is detected

**Response format:**
- Times sorted by UTC offset (west to east)
- Day transition markers when time crosses midnight (+1 / -1)
- Grouping by timezone — users in same location shown together
- Country flags for visual clarity

---

## Architecture

```
Telegram Group
      |
      v
+--------------------------------------------------+
|                    BOT CORE                      |
|  +----------+   +-----------+   +-----------+    |
|  | Capture  |-->| Transform |-->| Formatter |    |
|  | (Regex)  |   | (UTC-Piv) |   | (Output)  |    |
|  +----------+   +-----------+   +-----------+    |
|        |              |                          |
|        +-------+------+                          |
|                v                                 |
|           +----------+                           |
|           | Storage  |                           |
|           | (SQLite) |                           |
|           +----------+                           |
+--------------------------------------------------+
```

**Modules:**
- **Capture** — regex-based time pattern detection (configurable via YAML)
- **Transform** — UTC-pivot conversion ensuring consistency with IANA timezone database
- **Formatter** — output formatting with grouping and day markers
- **Storage** — SQLite for users and chat membership
- **Geocoding** — city name to timezone resolution (geopy + timezonefinder)

---

## MVP Status

This is a Minimum Viable Product release.
**Scope:** Telegram only (Discord support planned for v0.2)

**Current limitations:**
- Platform: Telegram only
- Detection: Regex-based; may miss complex natural language expressions (e.g., "quarter past five")
- Storage: SQLite (lightweight, no external dependencies)

---

## Roadmap

**Planned improvements:**
- Discord support via platform adapter
- Fuzzy city detection using Levenshtein distance (rapidfuzz) to handle typos
- Global error handling with Sentry integration

---

## Tech Stack

- **Python 3.12+** — runtime
- **aiogram** — async Telegram Bot API
- **aiosqlite** — async SQLite interface
- **zoneinfo / tzdata** — IANA timezone database
- **geopy / timezonefinder** — geocoding pipeline
- **PyYAML / python-dotenv** — configuration
- **uv** — package management
- **ruff** — linter & formatter

---

## Quick Start

See [ONBOARDING.md](docs/ONBOARDING.md) for installation and configuration.

---

## License

MIT
