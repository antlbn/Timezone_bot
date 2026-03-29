# 14. LLM Module

## 1. Purpose

The LLM is the mandatory event-detection and extraction layer for the Timezone Bot MVP.
It decides whether a message represents a time coordination event and returns structured data for downstream conversion.

## 2. Architectural Position

- LLM usage is mandatory for the core message flow.
- There is no regex-first path and no regex fallback path in MVP.
- The LLM does not send replies directly; it returns structured output to the bot logic.
- Production runtime should support a primary LLM and an optional fallback LLM for resilience.

## 3. Input to the LLM

The LLM receives:

- current message,
- anchor timestamp.

The module is platform-agnostic. Telegram and Discord messages are normalized before prompt construction.

## 4. Output Contract

The LLM must return structured JSON with at least:

- `event: boolean`
- `points: []`

Each point contains:

- `time: HH:MM`
- `city: string | null`
- `event_title: string | null`

`city` is the per-point source-location override for the current message only.
`event_title` is optional presentation metadata only.

## 5. Runtime Rules

### 5.1 `event=false`

- no conversion,
- no onboarding,
- stop.

### 5.2 `event=true`

The bot proceeds according to sender registration state:

- registered sender -> normal conversion path,
- unregistered sender -> freeze message and start onboarding.

## 6. Source Time Interpretation

The LLM may extract:

- one or more time points,
- optional per-point `city`,
- optional `event_title` attached to the relevant point or block.

The LLM does not persist any user profile data.
If `city` exists, the downstream runtime may use it as the source-time override for the current message only.
If `event_title` exists, it is presentation metadata only and must not affect conversion eligibility.

## 7. Unknown Sender Rule

When `event=true` for an unknown sender:

1. freeze the message,
2. start onboarding asynchronously,
3. wait for onboarding outcome before deciding whether the message can be converted.

Outcome handling:

| Outcome | Runtime consequence |
|---|---|
| Onboarding completed | Save timezone and process frozen message |
| Onboarding declined | Process frozen message only if point `city` is sufficient |
| Onboarding ignored / timeout | Discard frozen message |

## 8. Guardrails

- The system should bias toward silence when uncertain.
- Max message length and max message age are enforced outside or around the LLM call.
- The LLM must not infer durable sender timezone from natural language.
- The LLM must not assume participant lists from conversation unless explicitly supported in future scope.
- If the primary LLM call fails, runtime may retry via a configured fallback LLM.
- Failed primary and fallback attempts must be logged with enough context to diagnose provider/model failure.
- Fallback switching must not change business rules; it changes only the provider/model used for the same contract.

## 9. Non-Goals

- recurring event scheduling,
- participant subset extraction,
- regex fallback for production behavior,
- updating sender DB timezone from per-message `city`.
