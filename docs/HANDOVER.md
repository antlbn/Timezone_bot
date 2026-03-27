# Handover: Architecture & Design Decisions

Technical "brain" of the project for future maintainers. For usage instructions see [ONBOARDING.md](ONBOARDING.md).

---

## 1. Core Concept: UTC-Pivot

All time conversions go through UTC to avoid N-to-N timezone complexity:

```
User time → Sender's TZ → UTC (pivot) → Each member's TZ
```

**Why:** Direct Local→Local conversions are error-prone and don't scale. Single pivot point simplifies DST handling.

### LLM Parallelism & Concurrency

The bot uses a **per-chat queuing system** to handle high-frequency messages without losing context or wasting tokens:
- **Individual Locks**: Every chat (`chat_id`) has its own `asyncio.Lock`. Messages within one chat are processed sequentially.
- **Cross-Chat Parallelism**: Different chats (e.g., Telegram Chat A and Discord Server B) are processed in parallel.
- **Cached LLM Runtime**: A cached `ChatOpenAI` client and a cached tool-bound runnable are reused across calls.
- **Shared Graph Runtime**: LangGraph is compiled once per process and reused with a shared `AsyncSqliteSaver` connection.

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

### 3.1 Why LLM for Event Detection?

| Approach | Verdict | Reasoning |
|----------|---------|-----------|
| **Regex** | ❌ Replaced | Limited to predefined formats. Misses context and natural language ("noon", "next Friday"). |
| **LLM** | ✅ Chosen | Handles ambiguity, multiple times, and natural language. Enforces schema via JSON output. |

### 3.2 Why Nominatim (OSM) Over Google Geocoding?

- **Free & unlimited** — no API key management
- **Built-in fuzzy matching** — handles typos
- **Understands disambiguations** — "Paris, Texas" → US timezone (not France)


### 3.3 Why Passive Collection Over Chat Member List?

Telegram bots can't list all chat members without admin rights. Instead:
- Bot records users as they send messages
- "Lurkers" won't appear in conversions — **expected behavior**

**Discord:** Uses same approach for consistency + `on_member_remove` event for cleanup.

### 3.4 Why Shared Runtime + Persisted Graph Memory Over Redis?

The bot keeps only lightweight runtime state in memory and stores agent reasoning memory in LangGraph checkpoints:
1.  **Users Cache**: Read-through **LRU snapshots** (Limit: 10k users) of SQLite data.
2.  **Graph Runtime**: Shared compiled LangGraph app + shared SQLite checkpointer.
3.  **LLM Queue**: Async locks per chat with **20s aging** to prevent stale responses.
4.  **Invite Cooldown State**: In-process timestamps that prevent repeated onboarding prompts.

| Factor | Decision |
|--------|----------|
| **Complexity** | Zero config — no Redis server required. |
| **UX** | Lazy onboarding — actionable unregistered messages can trigger setup, but old messages are never replayed later. |
| **Safety** | Per-chat locks prevent data race and LLM token waste. |

### 3.5 Why SQLite Over PostgreSQL?

- **Zero setup** — comes with Python
- **Async via aiosqlite** — fast enough for single-instance
- **Persistent Connection** — Reuse single DB handle for the lifetime of the process.
- **WAL (Write-Ahead Logging)** — Global PRAGMA for high concurrency.
- **Multi-platform ready** — `platform` column separates Telegram/Discord users

### 3.6 Timestamp Consistency (Zulu Format)

To ensure perfect alignment between production adapters and evaluation test cases:
- **Format**: All internal timestamps (`timestamp_utc`) **MUST** use the ISO 8601 Zulu format: `YYYY-MM-DDTHH:MM:SSZ`.
- **Generation**: Use `.strftime('%Y-%m-%dT%H:%M:%SZ')` in adapters. Avoid `isoformat()` which may include redundant offsets (e.g., `+00:00`).
- **Parsing**: Use `dateutil.parser.isoparse()` for robust parsing in the event detection pipeline.

---

## 4. Component Overview

| Module | Purpose |
|--------|---------|
| `src/event_detection/` | LLM orchestration, LangGraph runtime, persisted thread memory, and per-chat locking |
| `src/transform.py` | UTC-Pivot conversions, IANA timezone database |
| `src/geo.py` | City → Coordinates → Timezone (Nominatim + TimezoneFinder) |
| `src/storage/` | SQLite + **In-Memory Caches & Pending Storage** |
| `src/formatter.py` | Response text generation, UTC offset sorting |
| `src/commands/` | Telegram handlers + FSM + Middleware |
| `src/discord/` | Discord handlers + UI (Views, Modals) |

---

## 5. Known Limitations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **Cold Start** | Caches empty on restart | Passively filled on first message/lookup. |
| **Platform Limits** | Discord buttons vs Telegram ForceReply | Unified core logic handles both variants. |

---

## 6. Future Roadmap

| Priority | Enhancement |
|----------|-------------|
| **High** | **LRU Cache + Activity Tracking**: **Implemented** (2026-03-16). |
| **Medium** | **Background Sync (Discord)**: **Implemented** (2026-03-15). |
| **Medium** | Dockerization for easy deployment |
| **Low** | WhatsApp support |

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
- [05_storage.md](../journal/05_storage.md) — DB schema, Clean Memory architecture
- [14_llm_module.md](../journal/14_llm_module.md) — LLM Event Detection pipeline
- [15_onboarding_capture.md](../journal/15_onboarding_capture.md) — Lazy onboarding boundary and no-replay rule
