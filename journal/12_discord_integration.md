# 12. Discord Integration

> [!NOTE]
> **Status: Implemented**

## 1. Overview

Bot extension to support Discord servers. Uses **discord.py** — async library with slash commands support.

### Architecture: Parallel Adapters

```
┌─────────────────┐     ┌─────────────────┐
│  Telegram API   │     │  Discord API    │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ src/commands/   │     │ src/discord/    │
│ (Telegram)      │     │ (Discord)       │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
         ┌───────────────────────┐
         │      SHARED CORE      │
         │  capture, transform,  │
         │  storage, geo, format │
         └───────────────────────┘
```

**Principle:** Platform adapters (Telegram/Discord) — thin layers. All logic in shared core.

---

## 2. Technology Stack

| Component | Library | Notes |
|-----------|---------|-------|
| **Discord API** | `discord.py` (2.x) | Async, slash commands, intents |
| **Commands** | Slash Commands | Modern Discord UX |
| **Storage** | Existing SQLite | `platform='discord'` |

---

## 3. Discord vs Telegram: Key Differences

| Aspect | Telegram | Discord |
|--------|----------|---------|
| **Set Timezone UX** | Text-based `/tb_settz` + ForceReply | Button → Modal (form) |
| **Fallback (city not found)** | Text reply with time | Buttons: "Try Again" / "Enter Time" |
| **Button security** | N/A | Only target user can click |
| **Stale user removal** | Manual `/tb_remove` | Auto-cleanup on time mention |
| **User exit detection** | Bot doesn't know (unless admin) | `on_member_remove` event |

### Button-Based Timezone Flow

In Discord, interactive elements are used instead of text responses:

1. **Unregistered user** mentions time → bot responds with a message containing **"Set Timezone"** button.
2. **Button is protected** — only the target user can click it (others get "This button is not for you!").
3. **Click** opens a modal window (form) for entering city.
4. **If city not found** — two buttons appear: "Try Again" and "Enter Time" (manual time input).

> [!IMPORTANT]
> Under the hood, the same function `geo.resolve_timezone_from_input()` is used as in Telegram.

---

## 4. Commands

| Command | Description |
|---------|-------------|
| `/tb_settz` | Set timezone (opens modal) |
| `/tb_me` | Show my timezone |
| `/tb_members` | List server members |
| `/tb_help` | Help message |

> [!NOTE]
> `/tb_remove` is **absent** in Discord — not needed thanks to auto-cleanup.

### Auto-Cleanup of Stale Members

On each time mention, bot checks if users from DB are still on the server:
- If user left the server (while bot was offline) — they are automatically removed from the list.
- This solves the problem of "stuck" users without manual intervention.

```python
# events.py - auto-cleanup logic
for m in db_members:
    if not message.guild.get_member(m["user_id"]):
        await storage.remove_chat_member(...)  # Auto-remove stale user
```

---

## 5. File Structure

```
src/discord/
├── __init__.py      # Bot instance, intents setup
├── commands.py      # Slash commands + handlers
├── ui.py            # UI components (Views, Modals)
└── events.py        # on_message (with auto-cleanup), on_member_remove
```

---

## 6. Configuration

**.env:**
```
TELEGRAM_TOKEN=...   # If set, Telegram bot starts
DISCORD_TOKEN=...    # If set, Discord bot starts
```

**Startup Logic (both platforms):**
- Token present → Bot starts
- Token missing → Skip with warning (no crash)

This approach allows running only needed bots — just set or remove the token.

---

## 7. Shared Core (No Changes Required)

| Module | Discord Compatibility |
|--------|----------------------|
| `capture.py` | ✅ Works as-is |
| `transform.py` | ✅ Works as-is |
| `storage/` | ✅ `platform='discord'` supported |
| `geo.py` | ✅ Works as-is |
| `formatter.py` | ✅ Works as-is |

---

## 8. Resolved Questions

- [x] **Separate codebase?** → No. Shared core, platform adapters.
- [x] **Bot per server?** → No. One bot instance, multi-server.
- [x] **Storage changes?** → No. `platform` column already exists.
- [x] **/tb_remove needed?** → No. Auto-cleanup handles stale users.
