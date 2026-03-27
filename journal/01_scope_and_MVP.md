# 01. Scope and MVP Specification

This document defines the product boundary for the current Timezone Bot MVP.

## 1. Product Goal

Build a stable bot for Telegram groups and Discord servers that:

1. tracks each participant's timezone,
2. detects time-coordination messages in normal conversation,
3. publishes one readable conversion message for the whole chat.

The product is for small and medium group coordination, not for full calendar management.

## 2. MVP Outcome

The MVP is successful if the system can reliably do the following:

1. accept onboarding and timezone setup on both platforms,
2. remember user settings across restarts,
3. detect actionable time mentions from normal chat text,
4. convert source time into local times for tracked chat members,
5. publish a new bot message or update the previous bot message for the same event,
6. avoid noisy onboarding behavior in active chats.

## 3. System Shape

The runtime is split into thin platform adapters and one shared core.

```text
Telegram updates ─┐
                  ├─> platform adapter ─> shared core ─> chat reply / edit
Discord updates ──┘                    ├> bot.db
                                       ├> graph_checkpoints.db
                                       ├> geocoding provider
                                       └> LLM provider
```

Shared core responsibilities:

- message orchestration,
- event detection via LangGraph agent,
- transformation and formatting,
- storage access,
- onboarding rules.

## 4. Core Product Rules

1. **Zero-friction chat usage**. Users should write natural messages. No special command syntax is required for normal time conversion.
2. **Registration before conversion**. A user must have a timezone before their message can produce a real published conversion.
3. **Gated execution before onboarding**. For unregistered users, the bot may reason about an actionable message, but must not execute real publish/update side effects before setup.
4. **No replay of old messages**. If a user completes onboarding later, the bot starts from the next message. It does not replay pre-onboarding chat messages.
5. **Per-chat sequential processing**. Within one chat, message handling is serialized to protect shared thread state.
6. **UTC-pivot transformation**. Time conversion uses IANA timezones and UTC as the canonical pivot.

## 5. In Scope

- Telegram group chats
- Telegram private chat for settings and onboarding
- Discord guilds
- Discord slash commands, buttons, and modals
- user timezone storage
- passive membership tracking for active participants
- detection of explicit and relative time mentions
- one message containing multiple time points
- chat-wide conversion output for known members
- bot message edit/update for follow-up corrections when the agent identifies the same event
- inactivity cleanup and stale-member cleanup

## 6. Out of Scope

- recurring schedules such as "every Tuesday at 10"
- Google Calendar / Outlook integration
- attendee subset extraction such as "only Alice and Bob"
- full historical replay after outages
- perfect reconstruction of missed short-term in-memory history after restart
- admin dashboards or multi-tenant web UI

## 7. Quality Bar

The MVP favors reliability over sophistication.

Required qualities:

- predictable onboarding behavior,
- low chat noise,
- safe failure mode when detection is uncertain,
- readable output on mobile,
- docs that are sufficient to rebuild the system.

## 8. Technology Direction

Current implementation direction:

- Python 3.12+
- `aiogram` for Telegram
- `discord.py` for Discord
- SQLite for product data
- SQLite LangGraph checkpoints for persisted thread state
- geocoding via `geopy` / `timezonefinder`
- LLM-backed event detection with tool-based action selection

## 9. Documentation Contract

The `journal/*.md` files are not project diary notes. They are the architectural and product specification set.

They must be good enough that, if the source code were lost, a new implementation team could rebuild the bot with the same runtime model and user-facing behavior.
