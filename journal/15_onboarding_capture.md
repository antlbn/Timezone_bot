# 15. Onboarding Detection Boundary

This document defines what happens when an unregistered user writes an actionable message.

## 1. Current Rule

The bot does **not** capture and replay the user's first actionable message anymore.

Instead:

1. the message is checked in detection-only mode,
2. if it is actionable, onboarding may be offered,
3. no conversion is published yet,
4. after setup, the bot starts from the user's next message.

## 2. Why This Rule Exists

This keeps the system simpler and more reliable:

- no backlog replay,
- no delayed reply to stale conversation,
- no extra queue to manage,
- no chance of replay running with shifted chat context.

## 3. Memory Boundary

Unregistered-user messages now go through the normal agent reasoning path.

The boundary is enforced in the action layer:

- the model may decide `publish_event` or `update_previous_event`,
- but real publish/update side effects are blocked,
- and thread memory gets an explicit app-logic marker instead of a fake publish/update result.

## 4. Invite State

The only onboarding-related transient state kept now is invite cooldown state.

It answers one question:

`Did we already invite this user recently on this platform?`

It does **not** store frozen chat messages for later replay.

## 5. Operational Consequence

If a user ignores onboarding and keeps chatting:

- the bot may detect more actionable messages,
- cooldown prevents repeated invites,
- no old messages are recovered later.

## 6. Rebuild Notes

If onboarding is rebuilt, preserve this simplification unless there is a strong product need for replay. The removed replay model added complexity and stale-context risks without enough UX benefit.
