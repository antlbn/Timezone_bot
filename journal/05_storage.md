# 05. Storage Module

## 1. Purpose

SQLite is the persistent store for user identity, timezone state, chat membership, and onboarding-related flags.

## 2. Storage Principles

- One shared SQLite database is used for Telegram and Discord.
- User identity is keyed by `(user_id, platform)`.
- Persistent timezone values use IANA names only.
- A user may exist in storage without a timezone if they were only passively observed or explicitly declined onboarding.
- Chat membership is tracked separately from user profile data.

## 3. Core Tables

### 3.1 `users`

```sql
CREATE TABLE users (
    user_id              INTEGER NOT NULL,
    platform             TEXT NOT NULL,           -- 'telegram' | 'discord'
    username             TEXT,
    timezone             TEXT,                    -- nullable until user completes setup
    city                 TEXT,
    flag                 TEXT DEFAULT '',
    onboarding_declined  INTEGER DEFAULT 0,       -- 1 when user explicitly refused setup
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now')),
    last_active_at       TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, platform)
);
```

### 3.2 `chat_members`

```sql
CREATE TABLE chat_members (
    chat_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    platform    TEXT NOT NULL,
    joined_at   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (chat_id, user_id, platform),
    FOREIGN KEY (user_id, platform) REFERENCES users(user_id, platform) ON DELETE CASCADE
);

CREATE INDEX idx_chat_members_chat ON chat_members(chat_id, platform);
```

## 4. Stored State Semantics

| Field | Meaning |
|---|---|
| `timezone` | User's saved IANA timezone; nullable before successful onboarding |
| `city` | Display city chosen or resolved during setup |
| `flag` | Optional display flag |
| `onboarding_declined` | Whether the user explicitly refused to share timezone |
| `last_active_at` | Updated on incoming messages and commands |

## 5. Business Rules

- `timezone IS NULL` means the user is known but not configured.
- `onboarding_declined = 1` means the bot should avoid immediate repeated prompting, subject to cooldown rules.
- `event_location` must never overwrite stored `timezone`.
- Conversion output must include only chat members with non-null stored timezone.
- Numeric offsets such as `UTC+3` are not valid persistent timezone values.

## 6. Required Operations

### User Operations

```python
get_user(user_id: int, platform: str) -> dict | None
upsert_user_identity(user_id: int, platform: str, username: str | None) -> None
set_user_timezone(user_id: int, platform: str, city: str, timezone: str, flag: str) -> None
set_onboarding_declined(user_id: int, platform: str, declined: bool) -> None
update_activity(user_id: int, platform: str) -> None
```

### Chat Membership Operations

```python
add_chat_member(chat_id: int, user_id: int, platform: str) -> None
remove_chat_member(chat_id: int, user_id: int, platform: str) -> None
clear_chat_members(chat_id: int, platform: str) -> None
get_chat_members(chat_id: int, platform: str) -> list[dict]
```

## 7. Membership Strategy

Passive collection is the MVP strategy.

Rules:

- when a user writes in a chat, ensure both `users` and `chat_members` records exist,
- when the bot learns a user left, remove only the `chat_members` row for that chat,
- when the bot is removed from a chat/server, clear membership for that chat/server only,
- do not delete shared user profile data just because one chat membership ended.

## 8. Query Expectations

### Known Members for Conversion

Queries that feed conversion output must filter to configured users only.

Example:

```sql
SELECT u.user_id, u.username, u.timezone, u.city, u.flag
FROM users u
JOIN chat_members cm
  ON u.user_id = cm.user_id
 AND u.platform = cm.platform
WHERE cm.chat_id = ?
  AND cm.platform = ?
  AND u.timezone IS NOT NULL;
```

### Sender Lookup

Sender lookup must return enough information to distinguish:

- unknown user,
- known but unconfigured user,
- configured user,
- user who explicitly declined onboarding.

## 9. Limitations

- users who never wrote in the chat are absent from storage,
- lurkers do not appear in conversion output,
- history for LLM context is not stored in SQLite.

## 10. In-Memory Caching Strategies

To reduce active I/O, the bot caches frequently requested SQLite data in memory:

1. **User Snapshot Cache (L1):** An LRU cache (e.g., 10,000 slots) tracks user configurations. It is populated on first read and explicitly invalidated whenever a user's configuration changes.
2. **Chat Members Cache (L2):** A TTL cache (e.g., 60 seconds) handles chat member lists. It intercepts bursty events from active chats. The cache is invalidated automatically upon any member join/leave operations.

## 11. File Location

Database file:

```text
./data/bot.db
```

## 12. Non-Goals

- storing timezone history,
- storing numeric UTC offsets as durable profile settings,
- persisting LLM message history,
- full participant lists independent of observed activity.
