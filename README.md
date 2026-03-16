# Timezone Bot

Passive timezone synchronization utility for distributed around globe teams.

---

## Goal

Eliminate manual timezone conversion in group chats. Bot detects time mentions and broadcasts equivalent times for all participants.

```
"Meet at 5pm"  ───>  Bot captures time  ───>  Reply with times for all members
                                              
                                              14:00 Berlin | 08:00 New York | 22:00 Tokyo
```

When someone mentions a time in the chat, the bot automatically:
- Detects the time pattern in the message
- Looks up timezones of all registered chat members
- Converts and broadcasts the time for everyone

### Use Cases

**1. Smart City Recognition**
```
Bot:  What city are you in?
User: Paris, Texas
Bot:  Set: Paris 🇺🇸 (America/Chicago)
```
The bot understands qualified toponyms — "Paris, Texas" vs "Paris".

**2. Automatic Time Conversion**
```
👤 Maria: Let's sync at 3pm tomorrow

🤖 Maria: 15:00 Berlin 🇩🇪 | 09:00 New York 🇺🇸 | 23:00 Tokyo 🇯🇵
   /tb_help
```

---

## Design Principles

**Zero-friction approach:**
- No commands needed for conversion — it happens automatically
- Plug-and-play — adding bot to group is the only setup
- Self-registration — user registers timezone once, remembered across all groups
- Minimal interference — bot responds only when time is detected

**Response format:**
- Day transition markers when time crosses midnight (+1 / -1)
- Grouping by timezone — users in same location shown together

---

## Architecture

```
Telegram Group                     Discord server
      |                                  |
      v                                  v
+--------------------------------------------------+
|                    BOT CORE                      |
|  +----------+   +-----------+   +-----------+    |
|  | Event    |-->| Transform |-->| Formatter |    |
|  | Detection|   | (UTC-Piv) |   | (Output)  |    |
|  | (LLM)     |   |           |   |           |    |
|  +----------+   +-----------+   +-----------+    |
|        |              |                          |
|        +-------+------+                          |
|                v                                 |
|           +----------+                           |
|           | Working  |                           |
|           | Memory   |                           |
|           | (In-Mem) |                           |
|           +----------+                           |
+--------------------------------------------------+
```

**Modules:**
- **Event Detection** — LLM-powered time and event extraction (JSON schema enforced)
- **Transform** — UTC-pivot conversion ensuring consistency with IANA timezone database
- **Formatter** — output formatting with grouping and day markers
- **Working Memory** — 4-layer in-memory architecture with LRU caching (Layer 1)
- **Storage** — SQLite (WAL mode, persistent connection) for persistent state
- **Geocoding** — city name to timezone resolution (geopy + timezonefinder)

---

## Current Status

**Stable Release** — Telegram + Discord supported.

| Feature | Status | Note |
|------------|------|------|
| **Detection** | ✅ LLM-Powered | Handles natural language ("quarter past five", "at noon") |
| **Queuing** | ✅ Per-chat Lock | Messages wait their turn, no concurrency loss |
| **Memory** | ✅ 4-Layer + LRU| High performance, size-limited (O(1) lookups) |
| **Storage** | ✅ SQLite | Persistent, high-concurrency (WAL mode) |

**Roadmap:** Dockerization, WhatsApp support.

---

## Tech Stack

Python 3.12+ · aiogram · discord.py · aiosqlite · zoneinfo · geopy · uv

---

## Quick Start

See [ONBOARDING.md](docs/ONBOARDING.md) for installation.

For architecture details: [HANDOVER.md](docs/HANDOVER.md)

---

## License

MIT
