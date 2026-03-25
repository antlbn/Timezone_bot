# Technical Spec: Storage

This document defines the persistent data model used by Timezone Bot.

---

## 1. Purpose

Storage is the source of truth for:

- user timezone settings,
- per-chat membership tracking,
- user inactivity cleanup,
- explicit onboarding refusal (`onboarding_declined`).

The bot does **not** persist full chat transcripts in the main application database.

Primary DB:

- `./data/bot.db`
- technology: SQLite via `aiosqlite`
- connection mode: shared async connection with WAL enabled

---

## 2. Schema

### 2.1 `users`

Represents a user on a specific platform.

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER,
    platform TEXT DEFAULT 'telegram',
    username TEXT DEFAULT '',
    city TEXT,
    timezone TEXT,
    flag TEXT DEFAULT '',
    onboarding_declined INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, platform)
)
```

#### Field meaning

| Field | Meaning |
|---|---|
| `user_id` | Platform-specific user ID |
| `platform` | `telegram` or `discord` |
| `username` | Best-effort display username |
| `city` | Display city name |
| `timezone` | IANA timezone, e.g. `Europe/Berlin` |
| `flag` | Country/region emoji |
| `onboarding_declined` | `1` if the user explicitly refused auto-onboarding |
| `created_at` | First row creation timestamp |
| `last_active_at` | Updated on normal activity |

### 2.2 `chat_members`

Maps a user to a chat/guild on a platform.

```sql
CREATE TABLE IF NOT EXISTS chat_members (
    chat_id INTEGER,
    user_id INTEGER,
    platform TEXT DEFAULT 'telegram',
    PRIMARY KEY (chat_id, user_id, platform),
    FOREIGN KEY (user_id, platform)
        REFERENCES users(user_id, platform)
        ON DELETE CASCADE
)
```

---

## 3. Storage Rules

### 3.1 Timezone format

`timezone` must be stored as an IANA timezone name.

Allowed:

- `Europe/Berlin`
- `America/New_York`

Not allowed as primary stored value:

- `UTC+3`
- raw numeric offsets

### 3.2 User identity

A user is unique by the pair:

- `(user_id, platform)`

This allows the same numeric platform ID to exist independently across Telegram and Discord.

### 3.3 Chat membership

Membership is tracked passively:

- Telegram: middleware + group events + just-in-time verification before final reply build
- Discord: message activity + guild/member events

This means the bot only knows about users it has actually observed.

### 3.4 Explicit refusal

If a user declines onboarding:

- `onboarding_declined=1`
- future automatic onboarding prompts are suppressed
- the user can still explicitly set timezone later

---

## 4. Application API

### 4.1 User operations

```python
get_user(user_id: int, platform: str) -> dict | None

set_user(
    user_id: int,
    platform: str,
    city: str | None,
    timezone: str | None,
    flag: str = "",
    username: str = "",
    onboarding_declined: bool = False,
) -> None

update_activity(user_id: int, platform: str) -> None
delete_inactive_users(days: int) -> int
```

### 4.2 Chat membership operations

```python
add_chat_member(chat_id: int, user_id: int, platform: str) -> None
get_chat_members(chat_id: int, platform: str) -> list[dict]
remove_chat_member(chat_id: int, user_id: int, platform: str) -> None
clear_chat_members(chat_id: int, platform: str) -> None
```

---

## 5. Membership Model

### 5.1 Passive collection

The bot does not require administrator access to fetch a full member roster.

Instead it builds membership over time:

| Event | Storage action |
|---|---|
| observed message from registered user | `add_chat_member(...)` |
| user leaves chat/guild | `remove_chat_member(...)` |
| bot removed from chat/guild | `clear_chat_members(...)` |
| Telegram stale record discovered during reply build | `remove_chat_member(...)` |

Implication:

- lurkers who never sent a message may not appear in conversion output.

This is expected behavior.

### 5.2 Bot removal

If the bot is kicked from a chat/guild:

- delete all `chat_members` rows for that chat;
- preserve `users` rows, because the same user may still belong to other chats.

---

## 6. Caching and Non-Persistent State

Persistent storage is only one part of the data layer.

### 6.1 User snapshot cache

The bot also uses an in-memory LRU cache for hot user reads:

- implementation: `src/storage/user_cache.py`
- purpose: avoid repeated `get_user(...)` hits for active users

### 6.2 What is not stored in `bot.db`

The following are **not** part of the main SQLite schema:

- short-term LLM chat history,
- LangGraph checkpoint state,
- invite cooldown state.

Those concerns belong elsewhere:

- short-term history: `src/event_detection/history.py`
- LangGraph checkpoints: `data/graph_checkpoints.db`
- invite cooldown state: `src/storage/pending.py`

---

## 7. Example Queries

### 7.1 Load tracked users of one chat

```sql
SELECT u.user_id, u.username, u.city, u.timezone, u.flag, u.platform
FROM chat_members cm
JOIN users u
  ON cm.user_id = u.user_id
 AND cm.platform = u.platform
WHERE cm.chat_id = ?
  AND cm.platform = ?;
```

### 7.2 Mark user as active

```sql
UPDATE users
SET last_active_at = CURRENT_TIMESTAMP
WHERE user_id = ?
  AND platform = ?;
```

### 7.3 Remove inactive users

```sql
DELETE FROM users
WHERE last_active_at < datetime('now', ?);
```

---

## 8. Rebuild Checklist

To recreate storage correctly, an implementation must preserve:

1. Composite key `(user_id, platform)` for users.
2. Composite key `(chat_id, user_id, platform)` for memberships.
3. `onboarding_declined` as persisted behavior control.
4. `last_active_at` for inactivity cleanup.
5. Passive membership accumulation instead of full roster sync assumptions.
