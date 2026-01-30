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

---

## 2. Core Workflow

### Trigger
Бот слушает все сообщения в чатах и проверяет на срабатывание capture module (обнаружение времени).

### Flow: Happy Path (юзер в БД)

```
1. [TRIGGER]     → Capture module находит время в сообщении
2. [LOOKUP]      → Проверка sender_id в SQLite
3. [FOUND]       → Получаем timezone отправителя
4. [SCAN]        → Получаем список других юзеров чата из БД
5. [TRANSFORM]   → Вызов TTM для конвертации во все зоны
6. [REPLY]       → Бот реплеит:
                   "14:00 Berlin 🇩🇪 | 08:00 New York 🇺🇸 | 22:00 Tokyo 🇯🇵"
```


### Flow: New User (юзера нет в БД)

```
1. [TRIGGER]     → Capture module находит время
2. [LOOKUP]      → Проверка sender_id в SQLite
3. [NOT FOUND]   → Юзер отсутствует в БД
4. [SAVE TIME]   → Сохраняем pending_time в FSM state
5. [ASK CITY]    → Бот спрашивает: "Reply with your city name:"
6. [PARSE]       → Попытка определить timezone по городу
   │
   ├─ [SUCCESS]  → Сохраняем в SQLite
   │              → "Set: Berlin 🇩🇪"
   │              → Используем pending_time для конвертации
   │              → "Anton: 15:00 Berlin 🇩🇪 | 09:00 New York 🇺🇸"
   │
   └─ [FAIL]     → "City not found: ..."
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

---

## 3. Resolved Questions

- [x] ~~Rate limiting для ответов бота?~~ → `cooldown_seconds` в конфиге (default: 0 = off)
- [x] ~~Приватные чаты vs групповые?~~ → Только групповые. Приватные не нужны.



