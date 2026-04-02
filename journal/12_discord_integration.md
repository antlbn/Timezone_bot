# 12. Discord Integration

## 1. Scope

This document defines Discord-specific behavior for the shared Timezone Bot core.

## 2. Platform Role

- Main usage happens in Discord servers.
- Private Discord chat is not a separate product mode.
- Discord onboarding uses native interaction UI instead of Telegram-style DM deep links.

## 3. Architecture

Discord is a thin adapter around the shared core:

- event detection,
- storage,
- geo resolution,
- transform,
- formatter,
- pending queue logic.

## 4. Discord-Specific UX

### Time Event from Registered User

- event is detected,
- source timezone is resolved,
- conversion reply is posted in the server.

### Time Event from Unknown User

- message is frozen,
- bot offers onboarding through Discord-native button and modal flow,
- if setup succeeds, the frozen message is released,
- if setup is declined, the frozen message is processed only when explicit source-location text (`tz_city`) is sufficient,
- if setup is ignored, the frozen message expires.

## 5. Commands

| Command | Purpose |
|---|---|
| `/tb_settz` | Start or restart timezone setup |
| `/tb_me` | Show current saved timezone |
| `/tb_members` | Show known server members |
| `/tb_help` | Show short usage help |

Discord does not require `/tb_remove` in MVP because stale membership cleanup is automated.

## 6. Membership Handling

- passive collection happens on incoming messages,
- periodic cleanup should remove members who left while the bot was offline,
- `on_guild_remove` clears membership for that guild only.

## 7. Security Rules

- interactive buttons and modals must apply only to the target user,
- one user must not be able to complete onboarding for another user,
- server membership cleanup must affect only bot storage.

## 8. Message Visibility and Lifetime

- Public onboarding invites in server channels may be short-lived.
- Interactive onboarding and settings UX should prefer ephemeral responses where platform capabilities allow it.
- Conversion replies are public shared-chat outputs and are not ephemeral by default.
- Ephemeral visibility is a delivery concern only; it must not change conversion logic or onboarding outcomes.

## 9. Non-Goals

- separate Discord-only business logic,
- durable DM support mode,
- persistent manual UTC-offset registration,
- updating stored timezone from runtime `tz_city`.
