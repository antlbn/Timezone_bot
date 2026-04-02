# 14. LLM Module

## 1. Purpose

The LLM is the mandatory event-detection and extraction layer for the Timezone Bot MVP.
It decides whether a message contains a usable clock-time reference and returns structured data for downstream conversion.

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

The LLM must return structured JSON with:

- `time_mentioned: boolean`
- `points: []`

Each point contains:

- `time: HH:MM`
- `tz_city: string | null`
- `event_title: string | null`
- `am_pm_clear: boolean`

`tz_city` is the per-point source-timezone override for the current message only.
`event_title` is optional presentation metadata only.
`am_pm_clear` defines whether the extracted point is unambiguous enough to be published without annotation.

## 5. Runtime Rules

### 5.1 `time_mentioned=false`

- no conversion,
- no onboarding,
- stop.

### 5.2 `time_mentioned=true`

The bot proceeds according to sender registration state:

- registered sender -> normal conversion path,
- unregistered sender -> freeze message and start onboarding.

### 5.3 Ambiguous AM/PM

- `am_pm_clear=true` -> publish normally
- `am_pm_clear=false` -> publish with `AM/PM🤔` on the source line
- mixed clear + ambiguous points -> publish both kinds in one reply, annotating only ambiguous points

## 6. Source Time Interpretation

The LLM may extract:

- one or more time points,
- optional per-point `tz_city`,
- optional `event_title`,
- per-point `am_pm_clear`.

`tz_city` means source-location text for that extracted point, not the sender's profile city.
It is used only to resolve the source timezone for the current message or point.
Examples:
- `"12:00 in London"` -> `tz_city="London"`
- `"7pm Berlin time"` -> `tz_city="Berlin"`

The LLM does not persist any user profile data.
If `tz_city` exists, the downstream runtime may use it as the source-time override for the current message only.
If `event_title` exists, it is presentation metadata only and must not affect conversion eligibility.

## 7. Unknown Sender Rule

When `time_mentioned=true` for an unknown sender:

1. freeze the message,
2. start onboarding asynchronously,
3. wait for onboarding outcome before deciding whether the message can be converted.

Outcome handling:

| Outcome | Runtime consequence |
|---|---|
| Onboarding completed | Save timezone and process frozen message |
| Onboarding declined | Process frozen message only if point `tz_city` is sufficient |
| Onboarding ignored / timeout | Discard frozen message |

## 8. Guardrails

- The system should bias toward silence when uncertain.
- Max message length and max message age are enforced outside or around the LLM call.
- The LLM must not infer durable sender timezone from natural language.
- The LLM must not assume participant lists from conversation unless explicitly supported in future scope.
- If the primary LLM call fails, runtime may retry via a configured fallback LLM.
- Failed primary and fallback attempts must be logged with enough context to diagnose provider/model failure.
- Fallback switching must not change business rules; it changes only the provider/model used for the same contract.

## 8.1 Malformed Output Policy

- Unparsable JSON, non-object JSON, or missing required top-level fields must fail safe to silence.
- Invalid individual points must be dropped instead of crashing the pipeline.
- Examples of invalid points: impossible times like `99:99`, wrong field types, missing `am_pm_clear`.
- If all points are dropped after validation, runtime must behave as `time_mentioned=false`.

## 8.2 Client Lifecycle

- The runtime should reuse async LLM clients across messages when provider endpoint and credentials are unchanged.
- Per-message recreation of the HTTP client / LLM client is not part of the canonical MVP design because it adds avoidable connection churn and latency.
- Config-derived LLM attempt plans may be cached, but that cache must be invalidated when config is reloaded in-process.
- Fallback attempts must reuse the same business contract and prompt contract as the primary attempt; only provider/model selection may differ.

## 9. Non-Goals

- recurring event scheduling,
- participant subset extraction,
- regex fallback for production behavior,
- updating sender DB timezone from per-message `tz_city`.
