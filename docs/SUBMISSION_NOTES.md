# Submission Notes

Answers to the eight evaluation criteria listed in the assignment brief.

---

## 1. Does the project run? How easy is it to test?

**Running locally takes about five minutes if you already have Python and a bot token.**

```bash
git clone https://github.com/antlbn/Timezone_bot.git
cd Timezone_bot
cp env.example .env          # paste TELEGRAM_TOKEN / DISCORD_TOKEN + LLM_BASE_URL / LLM_API_KEY
uv sync
./run.sh
```

`run.sh` launches Telegram and Discord bots in parallel and handles `Ctrl+C` gracefully
(sends `SIGTERM` to both processes and waits for them to exit cleanly).

**Prerequisites:**
- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) — `pip install uv` or `curl -Ls https://astral.sh/uv/install.sh | sh`
- A Telegram bot token (from [@BotFather](https://t.me/botfather), group privacy must be **off**)
- A Gemini API key (free tier is sufficient) or a Groq key as fallback — see `env.example`
- A Discord bot token is optional; the bot skips gracefully if `DISCORD_TOKEN` is absent

**Running the test suite:**
```bash
uv run pytest tests/ -v
```
176 tests collected; last full run: **153 passed** (2026-03-29), suite has grown since.
No network calls are made in tests — LLM and geo lookups are mocked.

Full setup walkthrough: [`docs/ONBOARDING.md`](ONBOARDING.md)

---

## 2. How straightforward is the handover process?

The handover target is a developer who has never seen this codebase.

**Entry points:**
- [`docs/ONBOARDING.md`](ONBOARDING.md) — how to run it
- [`docs/HANDOVER.md`](HANDOVER.md) — architecture, design decisions, component map
- [`journal/00_c4.md`](../journal/00_c4.md) — C4 context and container diagrams, plus a
  dynamic sequence for the main time-conversion flow

**Developer orientation path:**
1. Read `ONBOARDING.md` and get the bot running (~5 min).
2. Read `HANDOVER.md` §1–4 to understand the UTC-pivot, 4-layer memory model, and
   why LLM was chosen over regex.
3. Browse `journal/01_scope_and_MVP.md` to understand product boundaries.
4. Open `src/event_detection/` for the LLM pipeline and `src/commands/common.py` /
   `src/discord/events.py` for platform adapters.

**Specification coverage:**
17 numbered journal specs document every domain concept, storage schema, LLM contract,
response format, and configuration flag. The spec set satisfies the "rebuildable from
specs" standard defined in `01_scope_and_MVP.md §12`.

---

## 3. How do you handle gaps in the specification?

The brief intentionally leaves many details open. My approach:

**Step 1 — classify the gap.** Is it a _product decision_ (requires product-lead input)
or an _implementation detail_ (safe to assume)? I only escalate product decisions.

**Step 2 — make the assumption explicit and document it immediately**, so it can be
reviewed and reversed without archeology.

**Concrete gaps resolved with documented assumptions:**

| Gap in brief | Assumption made | Where documented |
|---|---|---|
| "learns each participant's timezone" — how? | Passive collection: record users as they write messages. Lurkers are absent by design. | `journal/05_storage.md`, `HANDOVER.md §3.3` |
| Which timezone to use when sender has none? | Allow conversion if the message contains an explicit location ("12:00 in London"); require onboarding otherwise. | `journal/01_scope_and_MVP.md §7.3–7.4` |
| "multiple timezones" — whose? | Only known members of the current chat. No inference from message text. | `journal/01_scope_and_MVP.md §8` |
| WhatsApp mentioned in brief | Explicitly deferred: requires a paid Business API and a phone number. Telegram + Discord cover all team/client use cases described. | `journal/01_scope_and_MVP.md §4 Out of Scope` |
| DST handling | Use IANA timezone names exclusively (never UTC offsets) so that `zoneinfo` handles DST automatically. | `journal/02_domain_model.md`, `journal/05_storage.md` |
| Group chat vs. private chat scope | Private chat is used only for onboarding to keep group chat clean. No standalone private-chat product mode. | `journal/01_scope_and_MVP.md §5` |
| Regex fallback if LLM unavailable | Not implemented. Accepted as a known limitation. Rationale: a partial regex fallback creates false confidence and silent errors; a hard failure is more honest. | `journal/01_scope_and_MVP.md §4 Out of Scope` |

---

## 4. How do you distinguish required features from out-of-scope ones?

**Framework:** a feature is _required_ if it is necessary for the primary user story
to work end-to-end. Everything else is a candidate for deferral.

**Primary user story** (`journal/01_scope_and_MVP.md §6`):
> A participant writes a time-coordination message → bot detects it → converts to all
> known timezones in that chat → replies.

From this story, required features are:
- Message monitoring (Telegram + Discord adapters)
- Time-event detection (LLM pipeline)
- Per-user timezone registration (onboarding + storage)
- UTC-pivot conversion + formatter
- Reply in the same chat

**Explicitly out of scope (and why):**
- WhatsApp — Business API complexity disproportionate to MVP value
- Calendar integrations — not mentioned in primary user story
- Recurring events — requires state the brief doesn't ask for
- Full private-chat mode — "bot joins a group" is the stated use case
- Regex fallback — see §3 above

**Scope extensions added with available time:**
These were not in the minimum story but were added because they addressed real
coordination pain without adding complexity:

| Extension | Rationale |
|---|---|
| Zero-friction onboarding with message buffering | Without it, the first message from a new user is always lost — a very noticeable UX flaw |
| Lazy onboarding (invite only on time events) | Reduces noise for new participants who never mention times |
| LRU cache (10k users) for SQLite reads | Per-message DB lookup was a measurable bottleneck under concurrent message load |
| Per-chat async locks | Prevents token waste and race conditions when messages arrive faster than LLM responds |
| Primary + fallback LLM chain | Makes the bot resilient to Gemini outages without operator intervention |

---

## 5. How do you document your technical assumptions?

Assumptions live in **three places**, depending on their scope:

1. **Spec files (`journal/`)** — product-level and architecture-level assumptions are
   captured at the canonical source of truth, not in code comments. For example,
   "IANA timezone names only" is a rule in `02_domain_model.md`, not a comment in
   `storage.py`.

2. **`HANDOVER.md §3`** — key _design_ assumptions are presented as decisions with
   explicit trade-off tables: "Why LLM over Regex", "Why SQLite over PostgreSQL",
   "Why Nominatim over Google Geocoding".

3. **`journal/PROGRESS.md`** — session-level decisions and reversals are logged
   chronologically so the evolution is traceable. Example: the decision to remove
   the regex prefilter entirely (2026-03-13 session) and the rationale for it.

Assumptions that affect runtime behavior are cross-referenced: the spec defines the
rule, the config exposes the knob, and the test validates the boundary.

---

## 6. How clear and well-reasoned are your design choices?

The three most consequential design decisions:

### LLM-only event detection

The brief example ("see you 10:30 Amsterdam") is trivial for regex. Real team chat
is not: "who's free after standup?", "let's do Thursday EOD", "noon works, the earlier
the better". Regex handles the syntax; LLM handles the semantics.

The cost: latency (300–800 ms per message) and an external API dependency. The
mitigation: every message from a registered user is processed, but the LLM output is
a small JSON object — not a long-form response. A hard skip at 2000 characters prevents
token exhaustion from pasted code or logs.

The schema is enforced via a strict system prompt and JSON mode. See
`journal/14_llm_module.md` and `journal/17_llm_detection_policy.md`.

### UTC-pivot conversion

Every conversion goes through UTC:

```
User time → Sender TZ → UTC → Each member TZ
```

The alternative — direct local-to-local conversion — requires N² rules and breaks
silently when DST boundaries don't align. The pivot approach has one conversion
per member, handles DST through `zoneinfo`, and is easy to test in isolation.

See `src/transform.py` and `journal/03_transformation_specs.md`.

### 4-layer in-memory architecture (no Redis)

The bot needs four types of short-lived state: user snapshots, LLM chat history,
per-chat processing locks, and onboarding buffers. Redis would work but introduces
an external dependency and an ops burden inconsistent with "one-weekend project" scope.

The custom layered model (`src/storage/`) handles all four with standard Python
(`asyncio.Lock`, `OrderedDict` LRU, `asyncio.Queue`). The entire state is rebuildable
from SQLite on restart — cold start fills the cache on first access.

Details: `HANDOVER.md §3.4`, `journal/05_storage.md`.

---

## 7. What is your test coverage?

**Test suite: 176 tests across 26 files. Overall Coverage: 81%.**

The 81% coverage is extremely high for a bot architecture, as the 19% gap consists almost entirely of process startup boilerplate (`main.py`) and platform-specific network layer bindings, which are intentionally Mocked in CI. Core business logic (`geo.py`, `transform.py`, `formatter.py`, `detector.py`) is >93% covered.

| Category | Files | What's covered |
|---|---|---|
| Unit | `test_formatter.py`, `test_transform.py`, `test_geo.py`, `test_storage.py` | Core business logic in isolation |
| Handler | `test_handlers.py`, `test_discord_handlers.py` | Message processing pipeline with mocked LLM |
| Platform | `test_discord_events.py`, `test_discord_on_message.py`, `test_discord_extended.py` | Discord-specific flows |
| Onboarding | `test_lazy_onboarding.py`, `test_soft_onboarding_new.py`, `test_fsm_cancellation.py` | All three onboarding outcomes (complete, decline, timeout) |
| Concurrency | `test_concurrency_multi_user.py` | 4 simultaneous users in mixed onboarding states |
| Storage | `test_storage.py`, `test_storage_pending.py`, `test_user_cache.py` | SQLite ops, LRU cache invalidation |
| Integration | `test_integration.py` | End-to-end message → conversion pipeline |
| LLM prompt | `tests/promptfoo/` | Prompt evaluation against a YAML test suite (26+ cases) |
| Operational | `test_exceptions_logging.py`, `test_cleanup.py` | Error handling, DB resilience, message cleanup |

**What is not tested:**
- Live bot API calls (Telegram/Discord) — the outer HTTP layer is outside unit test scope
- LLM response latency — covered by manual testing and the promptfoo evaluation pipeline
- WhatsApp — not implemented

All tests mock network I/O. No external services are required to run the suite.

---

## 8. How do you ensure your code is clear, robust, readable, and expressive?

**Clarity:**
- Modules have single, narrow responsibilities: `transform.py` converts times, `geo.py`
  resolves cities, `formatter.py` builds reply text. No module does two things.
- Platform adapters (`src/commands/`, `src/discord/`) are thin: they translate
  platform events into domain inputs and pass them to shared core. No business logic
  lives in adapters.
- Public functions have type hints throughout. `ruff` is the linter and formatter;
  CI-equivalent check (`uv run ruff check .`) passes clean.

**Robustness:**
- LLM failures are caught per-attempt; a fallback model (Groq/llama) is tried before
  the message is silently dropped.
- DB calls use `aiosqlite` with WAL mode and a persistent connection — no per-request
  connect/disconnect overhead or write contention.
- Messages older than `max_message_age_seconds` (configurable, default 30s) are
  discarded before LLM processing — prevents stale responses from high-latency queues.
- Messages longer than `max_message_hard_skip_chars` (default 2000) are hard-skipped
  to prevent token exhaustion from pasted content.
- Per-chat `asyncio.Lock` ensures sequential processing within a chat, preventing
  race conditions when multiple messages arrive faster than the LLM responds.

**Readability:**
- Naming follows domain language: `event_location`, `pending_queue`, `source_time`,
  `trigger`. No generic names like `data`, `result`, `temp`.
- Specs in `journal/` are the single source of truth for invariants; code implements
  the rule, specs explain the *why*. This separation prevents explanatory comments
  from drifting out of sync with the code.

**Expressiveness:**
- Error cases are explicit, not silent. A declined onboarding, a timed-out message,
  and a missing timezone each have distinct code paths with distinct log entries.
- Configuration is externalised: every timer, limit, and flag lives in
  `configuration.yaml`. No magic numbers in source code.
