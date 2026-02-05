# 12. Discord Integration

> [!NOTE]
> **Status: Specified, not implemented**

## 1. Overview

Расширение бота для поддержки Discord серверов. Используем **discord.py** — зрелую async библиотеку с поддержкой slash commands.

### Architecture Approach: Parallel Adapters

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

**Принцип:** Platform adapters (Telegram/Discord) — тонкие слои. Вся логика в shared core.

---

## 2. Technology Stack

| Component | Library | Notes |
|-----------|---------|-------|
| **Discord API** | `discord.py` (2.x) | Async, slash commands, intents |
| **Commands** | Slash Commands | Modern Discord UX |
| **Storage** | Existing SQLite | `platform='discord'` already supported |

---

## 3. Discord-Specific Concepts

| Telegram | Discord | Notes |
|----------|---------|-------|
| Chat ID | Guild ID + Channel ID | Discord has servers (guilds) |
| User ID | User ID | Snowflake (int64) |
| @username | Display Name | Discord usernames are unique |
| Reply | Message Reference | Similar concept |
| ForceReply | Modals / Follow-up | Different UX pattern |

---

## 4. Commands Mapping

| Command | Description |
|---------|-------------|
| `/tb_settz` | Set timezone |
| `/tb_me` | Show my timezone |
| `/tb_members` | List chat members |
| `/tb_remove` | Remove timezone |
| `/tb_help` | Help message |

**Команды идентичны Telegram** — единый UX для обеих платформ.

---

## 5. Implementation Plan

### 5.1 New Files

```
src/discord/
├── __init__.py      # Discord bot setup, intents
├── commands.py      # Slash command handlers
├── events.py        # on_message, on_member_remove
└── utils.py         # Discord-specific helpers
```

### 5.2 Shared Core (No Changes)

| Module | Discord Compatibility |
|--------|----------------------|
| `capture.py` | ✅ Works as-is (text → time) |
| `transform.py` | ✅ Works as-is (UTC pivot) |
| `storage/` | ✅ Already supports `platform='discord'` |
| `geo.py` | ✅ Works as-is (city → tz) |
| `formatter.py` | ⚠️ May need Discord-specific formatting |

### 5.3 Entry Point

Отдельный entry point для Discord бота:

```python
# src/discord_main.py
from src.discord import bot
bot.run(os.getenv("DISCORD_TOKEN"))
```

Можно запускать оба бота параллельно или выбрать один.

---

## 6. Configuration & Startup Logic

**configuration.yaml:**
```yaml
telegram:
  enabled: true

discord:
  enabled: true
```

**.env:**
```
TELEGRAM_TOKEN=...
DISCORD_TOKEN=...
```

**Startup Logic:**

| Flag | Token | Result |
|------|-------|--------|
| `enabled: true` | ✅ Present | Bot starts |
| `enabled: true` | ❌ Missing | Skip + log warning |
| `enabled: false` | Any | Skip |

Такой подход: если флаг стоит, но токена нет — бот просто не запускается для этой платформы (не crash).

---

## 7. Gaps & Changes Required

### 7.1 Existing Specs to Update

| Spec | Change |
|------|--------|
| `01_scope_and_MVP.md` | Move Discord from "Out of Scope" to supported |
| `11_implementation_mapping.md` | Add Discord module mapping |

### 7.2 Existing Code to Modify

| File | Change |
|------|--------|
| `formatter.py` | Add Discord-specific output format (optional) |
| `configuration.yaml` | Add `discord` section |
| `env.example` | Add `DISCORD_TOKEN` |

### 7.3 New Code to Create

| File | Purpose |
|------|---------|
| `src/discord/__init__.py` | Bot instance, intents setup |
| `src/discord/commands.py` | Slash command handlers |
| `src/discord/events.py` | Message events, member tracking |
| `src/discord_main.py` | Entry point |

---

## 8. Trade-offs

| Aspect | Decision | Reasoning |
|--------|----------|-----------|
| **Separate entry point** | Yes | Simpler than unified runner |
| **Slash commands only** | Yes | Modern Discord UX, no prefix needed |
| **Shared formatter** | Maybe | Discord supports embeds, may want richer output |

---

## 9. Out of Scope (This Iteration)

- Discord-specific features (embeds, buttons, reactions)
- Voice channel integration
- Thread support
- Multi-server bot settings

---

## 10. Verification Plan

### Unit Tests
- Reuse existing tests for shared core
- Add Discord-specific mocks for `discord.py` objects

### Integration Test
- Deploy test Discord bot
- Manual: `/settz Berlin`, send "meeting at 15:00", verify response

---

## 11. Resolved Questions

- [x] **Separate codebase?** → No. Shared core, platform adapters.
- [x] **Bot per server?** → No. One bot instance, multi-server.
- [x] **Storage changes?** → No. `platform` column already exists.
