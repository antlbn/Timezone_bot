# Handover: Architecture & Design Decisions

Technical "brain" of the project for future maintainers. For usage instructions see [ONBOARDING.md](ONBOARDING.md).

---

## 1. Core Concept: UTC-Pivot

All time conversions go through UTC to avoid N-to-N timezone complexity:

```
User time → Sender's TZ → UTC (pivot) → Each member's TZ
```

**Why:** Direct Local→Local conversions are error-prone and don't scale. Single pivot point simplifies DST handling.

---

## 2. Platform Architecture

```
┌─────────────┐     ┌─────────────┐
│  Telegram   │     │  Discord    │
│  (aiogram)  │     │(discord.py) │
└──────┬──────┘     └──────┬──────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│src/commands/│     │src/discord/ │
│  + FSM      │     │  + Modals   │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 ▼
       ┌───────────────────┐
       │    SHARED CORE    │
       │ capture|transform │
       │ storage|geo|format│
       └───────────────────┘
```

**Principle:** Platform adapters are thin. All business logic lives in shared core.

### Platform Differences

| Aspect | Telegram | Discord |
|--------|----------|---------|
| **Timezone Setup** | Text + ForceReply (FSM) | Button → Modal |
| **State** | `MemoryStorage` (FSM) | Stateless (modals) |
| **Stale Users** | Manual `/tb_remove` | Auto-cleanup on mention |
| **Leave Detection** | Bot doesn't know | `on_member_remove` event |

---

## 3. Key Design Decisions

### 3.1 Why Regex Over LLM/Fuzzy?

| Approach | Verdict | Reasoning |
|----------|---------|-----------|
| **Regex** | ✅ Chosen | Work chats use conventional formats (`10am`, `14:00`). Predictable, zero cost. |
| **rapidfuzz** | ❌ Rejected | Experimented with it. Natural phrases ("в полдень") are rare and cause false positives. |
| **LLM** | ❌ Overkill | Expensive per-message. Makes sense only if high accuracy for natural language is critical. |

### 3.2 Why Nominatim (OSM) Over Google Geocoding?

- **Free & unlimited** — no API key management
- **Built-in fuzzy matching** — handles typos
- **Understands disambiguations** — "Paris, Texas" → US timezone (not France)


### 3.3 Why Passive Collection Over Chat Member List?

Telegram bots can't list all chat members without admin rights. Instead:
- Bot records users as they send messages
- "Lurkers" won't appear in conversions — **expected behavior**

**Discord:** Uses same approach for consistency + `on_member_remove` event for cleanup.

### 3.4 Why MemoryStorage Over Redis?

| Factor | Decision |
|--------|----------|
| **Complexity** | `MemoryStorage` — zero config, built into aiogram |
| **Scale** | Single-instance bot, doesn't need distributed state |
| **Trade-off** | FSM state lost on restart. User just re-enters city — acceptable for MVP. |

### 3.5 Why SQLite Over PostgreSQL?

- **Zero setup** — comes with Python
- **Async via aiosqlite** — fast enough for single-instance
- **Multi-platform ready** — `platform` column separates Telegram/Discord users

---

## 4. Component Overview

| Module | Purpose |
|--------|---------|
| `src/capture.py` | Regex time extraction (patterns in `configuration.yaml`) |
| `src/transform.py` | UTC-Pivot conversions, IANA timezone database |
| `src/geo.py` | City → Coordinates → Timezone (Nominatim + TimezoneFinder) |
| `src/storage/` | SQLite: `users` + `chat_members` tables |
| `src/formatter.py` | Response text generation, UTC offset sorting |
| `src/commands/` | Telegram handlers + FSM + Middleware |
| `src/discord/` | Discord handlers + UI (Views, Modals) |

---

## 5. Known Limitations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **Cooldown in-memory** | Resets on restart | Acceptable for MVP. Move to DB/Redis if needed. |
| **FSM state lost on restart** | User re-enters city | Minor UX inconvenience. Redis can fix. |
| **No natural language times** | "at noon" not detected | Regex covers 95% of work chat patterns. |
| **Direct SQLite I/O** | Disk read per message | Design ready for cache layer ([05_storage.md §9](../journal/05_storage.md) — **not implemented**). |

---

## 6. Future Roadmap

| Priority | Enhancement |
|----------|-------------|
| **High** | Dockerization for easy deployment |
| **Medium** | In-memory DB cache (Write-Through) |
| **Medium** | Persistent FSM state (Redis) |
| **Low** | Lightweight LLM layer for natural language fallback |

---

## 7. Testing

- **Zero config:** Tests use temporary SQLite DBs
- **Run:** `uv run pytest` or `./run.sh test`
- **Coverage:** Core modules (capture, transform, storage, geo)

---

## 8. Configuration

| File | Contents |
|------|----------|
| `.env` | Tokens: `TELEGRAM_TOKEN`, `DISCORD_TOKEN` (set one or both) |
| `configuration.yaml` | Regex patterns, cooldown, display limits |

**Startup logic:** Token present → bot starts. Token missing → skip with warning.

---

## 9. Specs Reference

Detailed specifications in `journal/`:
- [01_scope_and_MVP.md](../journal/01_scope_and_MVP.md) — Project scope, tech stack
- [02_capture_logic.md](../journal/02_capture_logic.md) — Time detection patterns
- [04_bot_logic.md](../journal/04_bot_logic.md) — Workflow diagrams, FSM flows
- [05_storage.md](../journal/05_storage.md) — DB schema, caching architecture
- [12_discord_integration.md](../journal/12_discord_integration.md) — Discord-specific UX decisions
