# 16. UX and Onboarding Specification

## 1. Goal

Onboarding must collect a user's timezone with minimal disruption to shared chat conversation.

## 2. UX Principles

- shared chats stay clean,
- setup starts only when needed,
- the user should not lose the meaning of the original coordination message,
- stale delayed replies must be avoided.

## 3. Trigger Rule

Onboarding starts only when both conditions are true:

1. the LLM detects a time coordination event,
2. the author does not have a stored timezone.

No onboarding is triggered for ordinary conversation with `trigger=false`.

## 4. Pending Message Rule

When onboarding starts, the original message is frozen.
It is not processed immediately.

The frozen message is later:

- released after successful onboarding,
- released after decline only if `event_location` makes the source timezone explicit,
- discarded after timeout or after decline without `event_location`.

## 5. Telegram UX

Telegram uses private onboarding via deep links.

Shared group behavior:

- post a minimal invite,
- auto-delete it after a short TTL,
- respect onboarding cooldown,
- keep the actual setup steps in private chat.

Private chat behavior:

- explain what the bot does,
- ask for city or place name,
- resolve timezone,
- save data and release pending message if setup succeeds.

## 6. Discord UX

Discord uses button and modal onboarding inside native Discord interaction flow.

Behavior:

- offer setup only to the target user,
- collect city or place name through modal input,
- save timezone and release pending message on success,
- do not create persistent public setup noise.

## 7. Outcome Matrix

| Outcome | Stored state | Pending message |
|---|---|---|
| Success | timezone saved, decline flag cleared | released |
| Decline | decline flag saved | released only with valid `event_location`, otherwise discarded |
| Ignore / timeout | no timezone saved | discarded |

## 8. Cooldown and Expiry

Expected configurable controls:

- onboarding cooldown before re-inviting,
- pending-message timeout,
- cleanup TTL for short-lived shared-chat system messages.

## 9. Privacy Semantics

- private chat exists only to collect timezone setup with lower noise,
- decline means the user does not want to share timezone now,
- the user may later onboard voluntarily.

## 10. Non-Goals

- full private-chat product mode,
- forcing setup before the user can continue normal conversation,
- keeping frozen messages forever,
- storing durable UTC offsets instead of IANA timezone.
