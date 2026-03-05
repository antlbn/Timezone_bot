# 01. Scope and MVP Specification  
## Scope: Telegram + Discord (v1.1)

## Core Development Principles
- **MVP-first**: Exclude everything that is not critically important.
- **Agentic Development**: Development relies on working with AI agents.
- **Spec-driven**: 
  - Primary sources of truth are `journal/XX_spec_name.md` files. 
  - They describe architectural and product decisions.
  - The agent relies on these specifications when writing code.
  - They serve as the basis for future documentation.
- **Iterative Process**:
  1. Writing specifications (specs).
  2. Running the agent and reviewing its plan.
  3. Reviewing code and results.
  4. Updating specs.
  5. Recording in `journal/PROGRESS.md` after each significant change.
- **Documentation**: `README.md` and other user documents are created closer to MVP readiness.

## We Are Building an MVP

### Objective
Create a stable Telegram / Discord bot that:
1. Works in group Telegram chats and Discord servers.
2. Remembers users' timezones.
3. Responds with an expanded message when time is mentioned, converting it for all participants.

### Architecture Overview

```
┌─────────────┐     ┌─────────────┐
│  Telegram   │     │  Discord    │
│   Group     │     │   Server    │
└──────┬──────┘     └──────┬──────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│ src/commands│     │ src/discord │
│ (Telegram)  │     │ (Discord)   │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 ▼
┌───────────────────────────────────────────────────┐
│                  SHARED CORE                       │
│  ┌──────────────────┐  ┌─────────┐  ┌──────────┐  │
│  │  Event Detector  │─▶│Transform│─▶│Formatter │  │
│  │  (LLM)           │  │(UTC-Pivot│  │(Response)│  │
│  └──────────────────┘  └─────────┘  └──────────┘  │
│       (trigger + times[] + event_location)         │
│                      │                             │
│       ┌──────────────┼──────────────┐              │
│       ▼              ▼              ▼              │
│  ┌─────────┐  ┌──────────────┐  ┌─────────┐       │
│  │   Geo   │  │   Storage    │  │  Config │       │
│  │(Geocode)│  │   (SQLite)   │  │  (YAML) │       │
│  └─────────┘  └──────────────┘  └─────────┘       │
└───────────────────────────────────────────────────┘
```

### Qualities
- **Simplicity**: Does not require complex actions from the user.
- **Detection**: Every message is evaluated by an **LLM-based Event Detector** that decides whether the bot should react (trigger / no trigger) and extracts relevant times and event location context.
- **Time Accuracy**: Transformation is resistant to seasonal shifts (IANA database).
- **Easy Administration**: Configuration via `.yaml` and `.env`.

---

## Technology Stack

### Core (Shared)

| Component | Library | Purpose |
|-----------|---------|---------| 
| Runtime | `python` 3.12+ | Includes `sqlite3` |
| Storage | `aiosqlite` | Async SQLite wrapper |
| Timezone | `zoneinfo`, `tzdata` | IANA timezone database |
| Geocoding | `geopy`, `timezonefinder` | City → Coords → Timezone |
| Config | `PyYAML`, `python-dotenv` | Configuration management |
| Package | `uv` | Dependency & env management |
| Linter | `ruff` | Fast Python linter & formatter |

### Telegram

| Component | Library | Purpose |
|-----------|---------|---------| 
| Bot API | `aiogram` | Async Telegram Bot wrapper |

### Discord

| Component | Library | Purpose |
|-----------|---------|---------| 
| Bot API | `discord.py` 2.x | Async Discord Bot wrapper |

---

## High-level Configuration

### Response Structure
- Clearly defined message schema.
- Unified time format.
- **Date Handling**: Marking if time transitions to the next day.
- **Grouping**: Matching timezones — time once, cities comma-separated.

### Algorithm
1. Every message is forwarded to the **LLM-based Event Detector** (`13_event_detection.md`).
2. If `trigger=true`: use `times[]` and optional `event_location` from LLM output.
3. If `event_location` is set: geocode it → use as source timezone pivot.
4. Any conversion goes through UTC (direct Local→Local is prohibited).

---

## Out of Scope (Beyond Current MVP)
- WhatsApp support
- Fuzzy matching for time detection (e.g. `rapidfuzz`)
- Combining multiple times into one message

---

## Constraints (What Not To Do)
- **No Hardcode**: No hardcoding of cities and timezones.
- **Limited LLM Usage**: LLM is used only as a trigger + extraction layer (binary decision + times + event_location). It does not replace geocoding or time conversion logic.
- **No Private Chats**: Bot works only in group chats/servers.
- **No DB Updates from event_location**: `event_location` is a one-time pivot; it never overwrites the sender's stored timezone.
