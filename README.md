# Timezone Bot

A passive, zero-friction utility for distributed teams to synchronize time across multiple timezones.

## Project Goal
To eliminate the mental load of manual timezone conversion in international group chats. The bot observes conversation, detects time mentions, and instantly broadcasts the equivalent time for all other participants in the chat.

## Mechanics
The system operates on a **UTC-Pivot** architecture:
1.  **Passive Capture**: Middleware monitors all incoming messages for time patterns (e.g., "15:00", "3 pm") using optimized Regex.
2.  **Normalization**: The captured time is combined with the sender's stored timezone to generate a UTC-aware timestamp.
3.  **Broadcasting**: This UTC timestamp is projected onto the timezones of all other active chat participants.

[Message "Let's meet at 5pm"] 
        │
   (Middleware Capture)
        │
(Sender TZ + "5pm") -> [UTC Pivot] -> (Member A TZ)
                                   -> (Member B TZ)
                                   -> (Member C TZ)

## Concept: Zero Friction
The solution prioritizes "invisibility". 
- **No Commands**: Users do not issuing commands to convert time.
- **Plug-and-Play**: Adding the bot to a group is the only setup step.
- **Self-Registration**: Users register their location once, and the bot remembers them across all shared groups.

## MVP Scope & Limitations
This release is a Minimum Viable Product with the following constraints:
- **Platform**: Telegram only.
- **Detection**: Regex-based. May miss complex natural language expressions (e.g., "quarter past five").
- **Persistence**: InMemory storage (SQLite for user profiles, but state is lightweight).
- **Interface**: Configuration requires replying to bot messages (current technical limitation).

## Roadmap
1.  **Multi-Platform Support**: Extensibility for Discord and WhatsApp adapters.
2.  **Fuzzy Detection**: Implementation of Levenshtein distance (`rapidfuzz`) to handle city name typos.
3.  **Dialogue UX**: Transition from "reply-only" interaction to inline buttons or ephemeral state tracking.
4.  **Error Middleware**: Global exception handling and administrative alerting (Sentry).

## Getting Started
For installation, configuration, and deployment instructions, refer to the documentation:

[👉 Onboarding & Installation Guide](docs/ONBOARDING.md)
