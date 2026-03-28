# 14. LLM Module

## 1. Purpose

The LLM is the mandatory event-detection and extraction layer for the Timezone Bot MVP.
It decides whether a message represents a time coordination event and returns structured data for downstream conversion.

## 2. Architectural Position

- LLM usage is mandatory for the core message flow.
- There is no regex-first path and no regex fallback path in MVP.
- The LLM does not send replies directly; it returns structured output to the bot logic.

## 3. Input to the LLM

The LLM receives:

- current message,
- limited recent chat history,
- sender metadata,
- sender stored timezone if present,
- anchor timestamp.

The module is platform-agnostic. Telegram and Discord messages are normalized before prompt construction.

## 4. Output Contract

The LLM must return structured JSON with at least:

- `trigger: boolean`
- `times: []`
- `event_location: string | null`

Optional fields may exist, but the runtime depends on these three.

## 5. Runtime Rules

### 5.1 `trigger=false`

- no conversion,
- no onboarding,
- message remains useful only as history.

### 5.2 `trigger=true`

The bot proceeds according to sender registration state:

- registered sender -> normal conversion path,
- unregistered sender -> freeze message and start onboarding.

## 6. Source Time Interpretation

The LLM may extract:

- one or more time points,
- optional `event_location`.

The LLM does not persist any user profile data.
If `event_location` exists, the downstream runtime may use it as the source-time override for the current message only.

## 7. Unknown Sender Rule

When `trigger=true` for an unknown sender:

1. freeze the message,
2. start onboarding asynchronously,
3. wait for onboarding outcome before deciding whether the message can be converted.

Outcome handling:

| Outcome | Runtime consequence |
|---|---|
| Onboarding completed | Save timezone and process frozen message |
| Onboarding declined | Process frozen message only if `event_location` is sufficient |
| Onboarding ignored / timeout | Discard frozen message |

## 8. History Rules

- History is in-memory only.
- History is scoped per chat.
- History is not persisted across restarts.
- A message may be appended to history even if it does not lead to a reply.

## 9. Guardrails

- The system should bias toward silence when uncertain.
- Max message length and max message age are enforced outside or around the LLM call.
- The LLM must not infer durable sender timezone from natural language.
- The LLM must not assume participant lists from conversation unless explicitly supported in future scope.

## 10. Non-Goals

- recurring event scheduling,
- participant subset extraction,
- persistent semantic memory,
- regex fallback for production behavior,
- updating sender DB timezone from `event_location`.
