# 12. Discord Integration

> [!NOTE]
> **Status: Implemented**

## 1. Overview

Расширение бота для поддержки Discord серверов. Используется **discord.py** — async библиотека с поддержкой slash commands.

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

**Принцип:** Platform adapters (Telegram/Discord) — тонкие слои. Вся логика в shared core.

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

В Discord вместо текстовых ответов используются интерактивные элементы:

1. **Незарегистрированный пользователь** упоминает время → бот отвечает сообщением с кнопкой **"Set Timezone"**.
2. **Кнопка защищена** — только целевой пользователь может её нажать (другие получат "This button is not for you!").
3. **Нажатие** открывает модальное окно (форму) для ввода города.
4. **Если город не найден** — появляются две кнопки: "Try Again" и "Enter Time" (ручной ввод времени).

> [!IMPORTANT]
> Под капотом используется та же функция `geo.resolve_timezone_from_input()` что и в Telegram.

---

## 4. Commands

| Command | Description |
|---------|-------------|
| `/tb_settz` | Set timezone (opens modal) |
| `/tb_me` | Show my timezone |
| `/tb_members` | List server members |
| `/tb_help` | Help message |

> [!NOTE]
> `/tb_remove` **отсутствует** в Discord — не нужна благодаря автоочистке.

### Auto-Cleanup of Stale Members

При каждом упоминании времени бот проверяет, находятся ли пользователи из БД ещё на сервере:
- Если пользователь покинул сервер (пока бот был выключен) — он автоматически удаляется из списка.
- Это решает проблему "зависших" пользователей без ручного вмешательства.

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
├── commands.py      # Slash commands + UI components (modals, views)
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

Такой подход позволяет запускать только нужных ботов — достаточно указать или убрать токен.

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
