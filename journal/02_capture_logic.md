# 02. Capture Logic Specification

This specification describes the logic for detecting time patterns in user messages.
We use a **Strict Regex Layer** as the primary and currently only method for MVP.

```
Message ──▶ [Regex Patterns] ──▶ Match?
                                   │
                        ┌──────────┴──────────┐
                        ▼                     ▼
                       Yes                   No
                        │                     │
                        ▼                     ▼
              ["19:00", "5 pm"]            (skip)
                        │ 
                        ▼
              → Transform Module
```

## 1. Concept
The agent must scan incoming messages for time patterns.
If a message contains one or more matches, they are extracted and passed to the next stage (conversion).


## 2. Supported Time Formats (Regex Patterns)

1.  **ISO-like / 24h format**: `HH:MM`
    *   Examples: `19:00`, `09:30`, `14:15`
2.  **12h format**: `H:MM AM/PM` or `H AM/PM` or `HH AM/PM`
    *   Examples: `5 PM`, `05:00 pm`, `10 am`, `9:30 PM` (case insensitive)


### Ignore Rules
*   We do **not** trigger on plain numbers (`19`, `5`). A separator `:` or marker `am/pm` is required.

### Example Regex
> **Note:** Exact patterns are defined in `configuration.yaml`.

*   `\b([0-1]?[0-9]|2[0-3]):([0-5][0-9])\b` — for `HH:MM`
*   `\b((1[0-2]|0?[1-9]):([0-5][0-9])\s?([AaPp][Mm]))\b` — for `12h` with minutes (with or without space)
*   `\b((1[0-2]|0?[1-9])\s?([AaPp][Mm]))\b` — for `12h` without minutes (e.g. `5 pm` or `10am`)

## 3. Handling Multiple Values
If a message contains multiple timestamps, the bot must extract all of them.

**Scenario:**
> "Let's call at 18:00 or maybe 19:30?"

**Parsing Result:**
`["18:00", "19:30"]`

The bot must convert each of these times.

## 4. Match Examples (Test Cases)

| User Message | Expected Result (list) | Comment |
| :--- | :--- | :--- |
| `Meeting at 15:00` | `["15:00"]` | Clean 24h match |
| `let's go at 19:00` | `["19:00"]` | Ignore preposition, take time |
| `Call me at 5 pm` | `["5 pm"]` | 12h format |
| `10:30 am or 11:30 am` | `["10:30 am", "11:30 am"]` | Multiple times |
| `Call at 14:00 MSK` | `["14:00"]` | "MSK" is parsed separately or ignored at this stage (MVP: take 14:00 as user's local time) |
| `Price 500` | `[]` | Not a time |
| `Score 12:45` | `["12:45"]` | **Edge Case**: looks like a match score. Regex will match. (We accept this risk for MVP) |

## 5. Implementation Instructions
1. Use Python's `re` module.
2. Extract the list of regular expressions to configuration.yaml.
3. Function `extract_times(text: str) -> List[str]` returns a list of found raw strings.
