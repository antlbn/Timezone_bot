# 08. Telegram Commands and UX

## 1. Scope

This document defines Telegram-specific behavior for group chats and Telegram-private onboarding.

## 2. Telegram Product Rules

- Main usage happens in Telegram groups.
- Private chat with the bot exists only for onboarding and timezone setup.
- Group chat should not be polluted by multi-step setup dialogs.
- The bot converts time only for known group members with stored timezones.

## 3. Commands

| Command | Scope | Purpose |
|---|---|---|
| `/tb_help` | Group or private | Show short usage help |
| `/tb_me` | Group or private | Show the user's saved timezone |
| `/tb_settz` | Group or private | Start or restart timezone setup in private chat |
| `/tb_members` | Group | Show known members of the current group |
| `/tb_remove` | Group | Remove a stale member from bot storage for this group |

## 4. Group-Time Event Behavior

When a Telegram group message contains a detected time coordination event:

- if the sender is registered, conversion is posted normally,
- if the sender is unknown, the bot posts a short-lived onboarding invite with a deep link to private chat,
- the original message is frozen until onboarding succeeds, is declined, or times out.

## 5. Onboarding UX

### 5.1 Group Invite

The group sees only a minimal onboarding invite, for example:

```text
Hi, tap below to set your timezone.
[Set up timezone]
```

Rules:

- invite is short-lived and auto-deleted,
- repeated invites are limited by `dm_onboarding_cooldown_seconds`,
- no multi-step city dialog happens in the shared chat.

### 5.2 Private Chat Flow

Private chat is used only for:

- welcome / purpose explanation,
- timezone setup,
- privacy notice,
- retry after invalid city input.

### 5.3 Outcome Rules

| Outcome | Result |
|---|---|
| Setup completed | User timezone is saved and pending message is released |
| Setup declined | Decline flag is saved; pending message is released only if `event_location` is sufficient |
| Setup ignored | Pending message expires and is discarded |

## 6. Command Behavior

### `/tb_help`

Shows concise product usage and points users to timezone setup.

### `/tb_me`

Returns the current saved timezone, city, and display metadata if available.

### `/tb_settz`

Starts private onboarding or restarts timezone setup.

Telegram rule:

- if invoked in a group, the bot should redirect the user to private chat,
- if invoked in private chat, the bot continues the setup flow directly.

### `/tb_members`

Shows only known members of the current group who have data in bot storage.

### `/tb_remove`

Removes a stale user from the bot's group membership records when automatic cleanup was insufficient.
This affects bot storage only, not real Telegram membership.

## 7. Cleanup Rules

- short-lived group invites are auto-deleted,
- command noise in groups should be minimized where practical,
- important reference messages in private onboarding may remain,
- transient prompts may be cleaned up according to configuration.

## 8. Security Rules

- deep-link payload must be validated,
- one user's onboarding link must not be usable by another user,
- group actions must not let one user set timezone for another user.

## 9. Telegram-Specific Non-Goals

- full onboarding inside a group chat,
- persistent private support mode,
- conversion for unknown members with no stored timezone,
- automatic update of stored timezone from time mention location text.
