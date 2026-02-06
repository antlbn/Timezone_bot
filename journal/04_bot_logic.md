# 🤖 Technical Spec: Bot Logic Module

## 1. Architecture Overview

```
┌─────────────────┐
│  Telegram API   │
└────────┬────────┘
         │ message
         ▼
┌────────────────────────────────────────────────────────┐
│                     BOT CORE                           │
│                                                        │
│  ┌─────────┐   ┌─────────────┐   ┌────────────────┐   │
│  │ Capture │──▶│ Transform   │──▶│ Response       │   │
│  │ (Regex) │   │ (UTC-Pivot) │   │ (Format)       │   │
│  └─────────┘   └─────────────┘   └────────────────┘   │
│       │                                               │
│       ▼                                               │
│  ┌──────────────────────────────────────────────┐    │
│  │              Storage (SQLite)                 │    │
│  │  users: timezone, city                        │    │
│  │  chat_members: who is in which chat           │    │
│  └──────────────────────────────────────────────┘    │
│       │                                               │
│       ▼ (if user not found)                          │
│  ┌─────────────┐                                     │
│  │ City → TZ   │ (Geocoding)                         │
│  └─────────────┘                                     │
└────────────────────────────────────────────────────────┘
         │
         ▼ reply
┌─────────────────┐
│  Telegram Chat  │
└─────────────────┘
```

### Integration Note
We leverage the standard **Telegram Bot API** via the **aiogram** library.
This ensures reliability and follows standard practices for handling:
- Message objects & updates (Long Polling)
- User & Chat entities
- Asynchronous event loop
- **ForceReply**: Auto-opens reply mode when bot asks for user input (improves UX)

---

## 2. Core Workflow

### Trigger
Bot listens to all messages in chats and checks for capture module triggers (time detection).

### Flow: Happy Path (user exists in DB)

```
1. [TRIGGER]     → Capture module finds time in message
2. [LOOKUP]      → Check sender_id in SQLite
3. [FOUND]       → Get sender's timezone
4. [SCAN]        → Get list of other chat users from DB
5. [TRANSFORM]   → Call TTM to convert to all zones
6. [REPLY]       → Bot replies:
                   "14:00 Berlin 🇩🇪 | 08:00 New York 🇺🇸 | 22:00 Tokyo 🇯🇵"
```


### Flow: New User (user not in DB)

```
1. [TRIGGER]     → Capture module finds time
2. [LOOKUP]      → Check sender_id in SQLite
3. [NOT FOUND]   → User not in DB
4. [SAVE TIME]   → Save pending_time in FSM state
5. [ASK CITY]    → Bot asks: "Reply with your city name:"
6. [PARSE]       → Attempt to determine timezone by city
   │
   ├─ [SUCCESS]  → Save to SQLite
   │              → "Set: Berlin 🇩🇪"
   │              → Use pending_time for conversion
   │              → "Anton: 15:00 Berlin 🇩🇪 | 09:00 New York 🇺🇸"
   │
   └─ [FAIL]     → "City not found. Reply with your current time (e.g. 14:30)
                    or try another city name:"
                 → User replies:
                    ├─ [TIME]  → Calculate offset, save UTC+X
                    └─ [CITY]  → Repeat geocoding
```

#### Sequence Diagram: New User Flow

```mermaid
sequenceDiagram
    participant U as User
    participant B as Bot
    participant DB as SQLite
    participant G as Geocoding

    U->>B: "Meeting at 15:00"
    B->>DB: get_user(user_id)
    DB-->>B: null (not found)
    Note over B: Save pending_time="15:00" in FSM
    B->>U: "Reply with your city:"
    U->>B: "Berlin"
    B->>G: geocode("Berlin")
    G-->>B: {tz: "Europe/Berlin", flag: "🇩🇪"}
    B->>DB: set_user(user_id, "Berlin", "Europe/Berlin")
    B->>DB: add_chat_member(chat_id, user_id)
    B->>U: "Set Anton: Berlin 🇩🇪 (Europe/Berlin)"
    Note over B: Use saved pending_time
    B->>DB: get_chat_members(chat_id)
    DB-->>B: [members with timezones]
    B->>U: "Anton: 15:00 Berlin 🇩🇪 | 09:00 New York 🇺🇸"
```

#### Sequence Diagram: Fallback Flow (City Not Found)

```mermaid
sequenceDiagram
    participant U as User
    participant B as Bot
    participant G as Geocoding

    U->>B: "xyzabc" (invalid city)
    B->>G: geocode("xyzabc")
    G-->>B: null (not found)
    B->>U: "City not found. Reply with time (14:30) or try another city:"
    
    alt User enters time
        U->>B: "14:30"
        Note over B: Calculate UTC offset
        Note over B: offset = user_time - UTC_now
        B->>U: "Set Anton: UTC+3 🌐 (Europe/Moscow)"
    else User enters city
        U->>B: "Paris"
        B->>G: geocode("Paris")
        G-->>B: {tz: "Europe/Paris", flag: "🇫🇷"}
        B->>U: "Set Anton: Paris 🇫🇷 (Europe/Paris)"
    end
```

---

## 3. Resolved Questions

- [x] ~~Rate limiting for bot responses?~~ → `cooldown_seconds` in config (default: 0 = off)
- [x] ~~Private chats vs group chats?~~ → Group only. Private not needed.
