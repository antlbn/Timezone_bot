# Timezone Bot

Passive timezone synchronization utility for distributed teams.

---

## Goal

Eliminate manual timezone conversion in group chats. The bot detects time mentions and replies with equivalent local times for registered participants.

```
"Meet at 5pm"  ───>  Bot detects time  ───>  Reply with times for all members

                                            14:00 Berlin | 08:00 New York | 22:00 Tokyo
```

When someone mentions a time in the chat, the bot automatically:
- detects the time mention in the message
- resolves the sender's timezone context
- converts the moment for all registered chat members
- posts a compact reply back into the conversation

### Use Cases

**1. Smart City Recognition**
```text
Bot:  What city are you in?
User: Paris, Texas
Bot:  Set: Paris, Texas -> America/Chicago
```

The bot understands qualified locations, not just bare city names.

**2. Automatic Time Conversion**
```text
Maria: Let's sync at 3pm tomorrow
Bot:   15:00 Berlin | 09:00 New York | 23:00 Tokyo
```

---

## User Experience

**Zero-friction approach:**
- no command is required for time conversion
- users register their city/timezone once
- after setup, conversion happens automatically
- Telegram and Discord use different UI primitives, but the shared behavior is the same

**Response format:**
- day transition markers when time crosses midnight (`+1` / `-1`)
- compact per-user or per-timezone output depending on the formatter

---

## Architecture

```text
Telegram Group                     Discord Server
      |                                  |
      v                                  v
+--------------------------------------------------+
|                    BOT CORE                      |
|  +----------+   +-----------+   +-----------+    |
|  | Event    |-->| Transform |-->| Formatter |    |
|  | Detection|   | (UTC-Piv) |   | (Output)  |    |
|  |  (LLM)   |   |           |   |           |    |
|  +----------+   +-----------+   +-----------+    |
|        |                                             |
|        v                                             |
|   +-------------+   +----------+   +------------+   |
|   |   Storage   |   |   Geo    |   | Runtime /  |   |
|   |  (SQLite)   |   |  lookup  |   | chat queue |   |
|   +-------------+   +----------+   +------------+   |
+--------------------------------------------------+
```

**Modules:**
- **Event Detection**: LLM-powered time and event extraction
- **Transform**: UTC-pivot conversion with IANA timezone data
- **Formatter**: response formatting for chat output
- **Storage**: SQLite-backed persistent state
- **Geocoding**: city name to timezone resolution
- **Runtime**: per-chat sequencing to avoid stale concurrent replies

---

## Tech Stack

Python 3.12+ · aiogram · discord.py · aiosqlite · LangChain-compatible LLM client · geopy · uv

---

## Quick Start

See [docs/ONBOARDING.md](docs/ONBOARDING.md) for setup and local run instructions.

For maintainer notes, see [docs/HANDOVER.md](docs/HANDOVER.md).

Detailed specs and design notes live in [journal/](journal/).

---

## License

MIT
