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
- **Dat| Key | Telegram | Discord |
|---|---|---|
| **Bot ID** | `@Timezone_Bot` | `TimezoneBot#0000` |
| **Logic** | Python 3.12 (standard) | Python 3.12 (standard) |
| **Storage** | SQLite + In-Memory Cache | SQLite + In-Memory Cache |
| **Platform** | `aiogram 3.x` | `discord.py 2.x` |

---

## 4. Technical Core & Principles

1.  **UTC-Pivot**: Transformations go through UTC. No numeric offsets in DB.
2.  **Zero-Friction Onboarding**: New users set their timezone in DMs (Telegram) or via Modals (Discord) to keep group chat pristine.
3.  **Passive Collection**: The bot grows its database only by active members who write messages.
4.  **LLM as Orchestrator**: LLM (OpenAI/Ollama) is the primary engine for event detection, time extraction, and intent classification.
5.  **Clean Chat Registry**: All setup and configuration messages have a short TTL (Auto-cleanup).

---

## 5. Scope (v2.0)

### In-Scope:
- **Zero-Friction Onboarding**: Users are invited to set their location via private messages when they first interact with a time coordination event.
- **Support for Private Chats**: DMs and personal chats are used for onboarding, settings management, and 1-on-1 HELP.
- **Passive Membership Tracking**: Automatic registration of users in the chat database when they send messages.
- **Multi-Platform Support**: Unified logic for Telegram groups and Discord servers.
- **Handling Multiple Times**: Support for various time formats and multiple time points in a single message.
- **Vertical Layout**: Results are displayed as a vertical list of timezone groups for optimal mobile readability.

### Out of Scope (Current):
- **Recurring Meetings**: "Every Tuesday at 10:00".
- **External Integration**: No Google Calendar / Outlook sync.
- **Participant Selection**: LLM doesn't yet extract specific lists of attendees (it shows the time for all known chat members).
- **History persistence**: History buffer is cleared on bot restart.
 in group chats/servers.
- **No DB Updates from event_location**: `event_location` is a one-time pivot; it never overwrites the sender's stored timezone.
