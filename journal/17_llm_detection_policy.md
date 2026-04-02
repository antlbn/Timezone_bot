# 17. LLM Detection Policy

## 1. Bot States

| `time_mentioned` | `am_pm_clear` | Bot behavior |
|---|---|---|
| false | — | stay silent |
| true | true | convert and publish normally |
| true | false | publish with `AM/PM?` |

Mixed messages may contain both clear and ambiguous points. The bot publishes both, annotating only ambiguous points.

## 2. `am_pm_clear` Rules

### Clear (`true`)

- hour > 12 (`17:00`, `23:59`)
- 4 digits in a row (`1500`, `1430`)
- `HH:MM` with `:` or `.`
- explicit marker: `am/pm`, `утра/вечера/дня/ночи`, `after lunch`, `tonight`, `matin`, `morgens`
- relative time resolved exactly (`через час`)
- bare hour where only one interpretation is inside working hours `06:00–22:00`
- `"today at X"` where one interpretation is already in the past and the future one is selected

### Ambiguous (`false`)

- bare hour where both AM and PM interpretations are inside working hours (`6–10`)

## 3. Working-Hours Heuristic

Working range: `06:00–22:00`

| Bare hour | AM | PM | Resolution |
|---|---|---|---|
| 1–5 | outside range | inside range | choose PM, `clear=true` |
| 6–10 | inside range | inside range | ambiguous, `clear=false` |
| 11–12 | inside range | outside range | choose AM, `clear=true` |

### Timestamp Resolution Layer

Applies only to `"today at X"`:

- if one interpretation is already in the past and the other is still in the future, choose the future one and mark `clear=true`
- do not apply this rule to explicit past references such as `"yesterday at 10"`

## 4. `time_mentioned=false`

Return `false` when:

- there is no clock-time reference
- only a date/day is mentioned
- the expression is impossible (`13 ночи`, `14 pm`, `13 after midnight`)
- the text is only a bot mention

## 5. Dual Timezone Policy

If one moment is expressed in two zones, keep only the last target zone.

Example:
- `"в 3 по мск, это 4 по Вене"` -> `time=04:00`, `tz_city=Вена`

## 6. Malformed Output Policy

The runtime must fail safe to silence when:

- JSON cannot be parsed
- the top-level object is not valid
- required top-level fields are missing or wrong-typed

Per-point validation rules:

- `time` must be real `HH:MM`
- `tz_city` must be `string | null`
- `event_title` must be `string | null`
- `am_pm_clear` must be boolean

Invalid points are dropped individually.
If no valid points remain, runtime behaves as `time_mentioned=false`.

## 7. Runtime Presentation Policy

- clear point -> normal conversion block
- ambiguous point -> same conversion block, but prefix the source line with `AM/PM?`
- annotation is presentation-only and does not change the extracted time value
