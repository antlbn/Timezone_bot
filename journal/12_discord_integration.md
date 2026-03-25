# 12. Discord Integration

This document specifies how the bot behaves on Discord and how the Discord adapter differs from Telegram.

## 1. Role of the Discord Adapter

Discord is a thin platform adapter over the shared core.

It is responsible for:

- receiving guild messages,
- exposing slash commands,
- rendering Discord-native onboarding UI,
- providing send/edit/delete callbacks to the shared event-processing pipeline,
- performing Discord-specific membership cleanup.

It should not duplicate business logic that already exists in the shared core.

## 2. Why Discord UX Is Different

Discord gives the bot better targeted interaction primitives than Telegram groups:

- buttons,
- modals,
- ephemeral responses.

Because of that, Discord onboarding stays inside Discord. It does not require DM deep links.

## 3. Runtime Flow

### 3.1 Registered user

1. guild message arrives,
2. adapter loads sender snapshot,
3. adapter calls `process_message(...)` with real `send_fn`, `edit_fn`, `delete_fn`,
4. shared core may publish or update a conversion message.

### 3.2 Unregistered user

1. guild message arrives,
2. adapter calls `process_message(...)` in detection-only mode by passing no publish callbacks,
3. if the message is actionable, the adapter shows the onboarding prompt,
4. no real chat conversion is published,
5. after setup, the bot starts from the user's next message.

## 4. Onboarding Contract

### 4.1 Trigger

When an unregistered user writes an actionable time-coordination message, the bot replies with a short onboarding prompt and a `Set Timezone` button.

### 4.2 Security

The onboarding view is user-targeted. If another user presses the button, they should get a refusal message and must not be able to alter someone else's setup.

### 4.3 Success path

On success:

- timezone is saved,
- user is added to the current guild membership set,
- success response confirms the saved timezone,
- success response explicitly says:
  `I'll start converting times from your next message.`

### 4.4 Decline path

If the user explicitly declines:

- persist `onboarding_declined=True`,
- suppress future automatic invites,
- allow later manual recovery through `/tb_settz`.

### 4.5 Invalid city fallback

If city resolution fails, Discord uses native follow-up UI:

- `Try Again`
- `Enter Time`

This keeps the user inside the onboarding flow without polluting the guild chat.

## 5. Commands

| Command | Purpose |
|---|---|
| `/tb_help` | Show help text. |
| `/tb_me` | Show the caller's current timezone. |
| `/tb_settz` | Set timezone by city input. |
| `/tb_members` | Show tracked guild members. |

There is currently **no implemented Discord slash command** for manual member removal. Discord relies on event-driven cleanup plus daily reconciliation instead.

## 6. Membership Maintenance

Discord has two cleanup paths:

1. immediate cleanup on `on_member_remove`,
2. scheduled daily reconciliation in `src/discord/tasks.py` for users who left while the bot was offline.

This is stronger than Telegram, because Discord exposes more reliable guild membership signals.

## 7. File Ownership

| File | Responsibility |
|---|---|
| `src/discord/events.py` | message handling, onboarding trigger, member leave handling |
| `src/discord/commands.py` | slash commands and shared command handlers |
| `src/discord/ui.py` | buttons, modals, fallback views |
| `src/discord/tasks.py` | daily member sync and inactive-user cleanup |

## 8. Rebuild Notes

If Discord support is rebuilt:

1. keep the adapter thin,
2. keep onboarding inside Discord UI primitives,
3. preserve detection-only behavior before registration,
4. do not replay old pre-onboarding messages,
5. preserve daily guild reconciliation in addition to event-driven cleanup.
