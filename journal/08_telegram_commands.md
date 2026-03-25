# 08. Telegram Commands and UI

This document specifies the Telegram-specific command surface and user interaction model.

## 1. Purpose

Telegram uses two distinct UX layers:

- group-chat interactions for normal conversation and lightweight prompts,
- private-chat interactions for onboarding and personal settings.

The group should stay clean. Stateful setup belongs in DM whenever possible.

## 2. Commands

| Command | Context | Purpose |
|---|---|---|
| `/tb_help` | group or DM | Show help and the right next step for the current context. |
| `/tb_me` | group or DM | Show the user's saved location/timezone. |
| `/tb_settz` | group or DM | Open or continue timezone setup. In groups it redirects to DM; in DM it opens the settings/onboarding flow. |
| `/tb_members` | group only | Show tracked members for the current chat. |
| `/tb_remove` | group only | Remove a stale member from the current chat's tracked membership list. |

## 3. Group UX

### 3.1 Normal time mention

1. User writes a normal message.
2. Adapter forwards it to the shared processing pipeline.
3. If the sender is registered, the bot may publish or update a conversion message.
4. If the sender is not registered and the message is actionable, the bot may send one onboarding invite if cooldown allows.

### 3.2 `/tb_help`

In a group, help should not dump a full personal setup wizard into the chat.

Expected behavior:

- explain what the bot does,
- show chat-management commands,
- provide a DM link or settings entry point.

### 3.3 `/tb_settz`

In a group, `/tb_settz` does not run a long setup flow inline.

Expected behavior:

- send one short reply with a deep link to the bot's DM,
- let the actual setup happen in private chat.

### 3.4 `/tb_members`

Lists tracked members known for the current chat. This is a DB-backed operational view, not a live platform roster.

### 3.5 `/tb_remove`

Used when chat membership in storage is stale and someone should be removed manually.

Current interaction model:

1. bot prints a numbered list,
2. user replies with a number,
3. bot removes the selected stored member from `chat_members`.

If the reply is not a number, the temporary removal state is cleared and the message falls back to normal time-message handling.

## 4. DM UX

### 4.1 `/start` with onboarding deep link

If the payload is `onboard_{user_id}_{chat_id}`:

1. validate that the clicking user matches `user_id`,
2. show the onboarding welcome,
3. offer:
   - `Set my city`
   - `No thanks`
   - `Data Privacy`

### 4.2 `/tb_settz` in DM

This is the normal settings entry point for an already known user and also the recovery path for a user who previously declined onboarding.

Expected behavior:

- if timezone exists: show settings menu,
- if timezone does not exist: show onboarding welcome.

### 4.3 City entry

City entry uses FSM state in DM:

1. bot asks for city,
2. user sends free text,
3. bot resolves timezone,
4. bot saves the record,
5. bot confirms the result and explicitly says:
   `I'll start converting times from your next message.`

### 4.4 Decline path

If the user taps `No thanks`:

- persist `onboarding_declined=True`,
- stop future automatic invites,
- keep manual recovery via `/tb_settz` or settings menu.

## 5. Cleanup Rules

Telegram cleanup is intentionally asymmetric:

- group invites and helper messages are temporary,
- DM onboarding and settings messages may remain for reference,
- the bot should not litter active groups with multi-step setup dialogue.

Config knobs:

- `settings_cleanup_timeout_seconds`
- `dm_onboarding_cooldown_seconds`

## 6. Rebuild Notes

If Telegram is rebuilt from scratch, preserve these invariants:

1. onboarding-heavy interaction belongs in DM, not group chat;
2. group `/tb_settz` is a redirect, not a full wizard;
3. no replay of old pre-onboarding messages after setup;
4. decline suppresses future automatic invites until the user opts in manually.
