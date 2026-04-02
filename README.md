# Timezone Bot

A bot that helps distributed teams coordinate time in group chats.

## Goal

Timezone Bot watches normal conversation in Telegram groups and Discord servers, detects time coordination messages, and replies with local time for known members of that chat.

Note: the current MVP intentionally uses `one-shot / one-message` LLM detection.

### Use Cases

**1. Source location in normal language**
```text
User: Let's do 12:00 in London
Bot: 12:00 London 🇬🇧 | 13:00 Berlin 🇩🇪 | 08:00 New York 🇺🇸
```

**2. Automatic group conversion**
```text
Maria: Let's sync at 3pm tomorrow

Bot: 15:00 Berlin 🇩🇪 | 09:00 New York 🇺🇸 | 23:00 Tokyo 🇯🇵
```

## Flow

```mermaid
flowchart LR
    A[Message in group chat] --> B[LLM detection]
    B --> C[Resolve source timezone]
    C --> D[Convert for known members]
    D --> E[Reply in chat]
```

## Docs

- [docs/ONBOARDING.md](/Users/johnwunderbellen/Timezone_bot/docs/ONBOARDING.md) — how to run the project locally
- [docs/HANDOVER.md](/Users/johnwunderbellen/Timezone_bot/docs/HANDOVER.md) — key decisions and architectural intent
- [journal/](/Users/johnwunderbellen/Timezone_bot/journal) — canonical specs and source of truth
