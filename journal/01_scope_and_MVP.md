# 01. Scope & MVP

**MVP Boundaries:**
- The bot parses time in chats via LLM and converts it for all known chat members.
- **Out of scope:** Chat-based configuration UI, persistence for incomplete onboarding sessions (they live in memory), calendar integrations.
- **Supported platforms:** Telegram, Discord (via abstract adapters).
