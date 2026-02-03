## 2026-02-03 (session) - docs and specs minor changes
- **Cleanup**: unused imports (`ruff`).
- **Cleanup**: .gitignored few files

## 2026-02-03 (session) - docs and specs minor changes
- **Docs**: Synchronize journal specifications and onboarding guide with the codebase
- **Cleanup**: Removed experimental auto-update logic (`update_tzdata`) from `main.py` and unused imports (`ruff`).

## 2026-02-03 (session 6) — Testing & Handlers 
- **Testing**: Implemented handler unit tests (`tests/test_handlers.py`) using mocks (L1.5 Layer).
- **Docs**: Clarified Test DB independence in `HANDOVER.md` and `10_testing_strategy.md`.
- **Docs**: Clarified Test DB independence in `HANDOVER.md` and `10_testing_strategy.md`.
- **Docs**: Added note that tests run on temporary DBs, safe for new clones.
- **Decision**: Deferred "CachedDb" (in-memory storage) to Future Roadmap (post-MVP).

## 2026-02-02 (session 5)
- **refactored** Rename `/tb_mytz` command to `/tb_me` and clarify database documentation details.

## 2026-02-02 (session 5)
- **Fixed** Few bugs realting to DB schema change
- **Cleanup** __pycache__

## 2026-02-02 (session 4)
- **Method decomposition** def test_formatter_reply - now deomposited (it was too large)

## 2026-02-02 (session 3)
- **Refactor**: Storage decoupled into `src/storage/` (SQLite + ABC).
- **Feature**: Multi-Platform support schema (added `platform` col).


## 2026-02-02 (session 2) — Robustness & Logging 🛡️
- **Refactor**: Added missing exception logging in `geo.py`, `middleware.py`, and `storage.py`
- **Docs**: Updated `09_logging.md` and `10_testing_strategy.md` specifications with error handling improvements
- **Testing**: Added automated tests in `tests/test_exceptions_logging.py` for API and DB resilience
- **Discussion**: Config reload strategy (theoretical discussion, decided current singleton is sufficient)

## 2026-02-02 (session 1) — Commands Refactoring 🏗️
- **Refactor**: Decomposed monolithic `src/commands.py` into `src/commands/` package:
  - `settings.py`: `/tb_settz`, `/tb_mytz`
  - `members.py`: `/tb_members`, `/tb_remove`
  - `common.py`: `/tb_help`, time capture, event handlers
  - `states.py` & `middleware.py`: Extracted to separate files
- **Spec**: Updated `11_implementation_mapping.md` with new directory structure
- **Docs**: Updated `HANDOVER.md` to reference new middleware path
- **Discussion**: Config reload strategy (theoretical discussion, decided current singleton is sufficient)


## 2026-01-31 (session 1)
- **Feature**:force-replay to chat messages (to prevent chaos)

## 2026-01-31 (session 1)
- **Documentation**:minor changes in README, ONBOARDING

## 2026-01-30 (session 9)
- **Documentation**:minor changes in HANDOVER.md

## 2026-01-30 (session 8)
- **Documentation**: Solit docs into `README` (overview), `ONBOARDING` (how to run), and `HANDOVER` (architecture).
- **Testing**: Implemented 47 unit/integration tests (100% pass).
  - Covered Regex capture, Time conversion, Formatter, and Storage (SQLite).
- **Fixed**: Regex patterns now support non-breaking spaces (`\u00a0`).
- **Dependencies**: Added `pytest-asyncio` to dev dependencies.

## 2026-01-30 (session 7)
- **Refactor**: middleware.py - moved to commands.py

## 2026-01-30 (session 6) - Bug with time printing fixed
- **Fixed**: Time normalization — "5 pm" → "17:00" in replies
  - Added `normalize_time()` in `formatter.py`
- **Backlog**: middleware.py cleanup — find better place in existing modules 

## 2026-01-30 (session 5) — Multi-Chat Bug Hunt 🐛
- **Bug**: User from Chat A not added to Chat B's members list
- **Fixed** Bug fixed 

- **Backlog**: when user tests time in format other then 14:00 (5 pm or other) show normalized in return message
- **Backlog**: to fix bug middleware.py was created - let's find better place somewhere in existing modules 

## 2026-01-30 (session 4) — Spec Police & Memory Wipe 🧹
- **Cooldown**: Bot now knows when to shut up! `cooldown_seconds` in config 🤫
- **Spec Audit 04-06**: Renamed functions so specs stop lying
  - Yeeted `delete_user` and `sync_chat_members` — unnecessary bureaucracy
- **Bot Kicked**: When bot gets kicked — it forgets the chat (but not users!)
  - `clear_chat_members(chat_id)` + mermaid diagram in spec 05
- **UX**: ⬆️ REPLY now screams at users louder
- **Spec Audit 07-09**: All good! Implemented `show_usernames` option 👀
- **Spec Audit 10-11**: Fixed run command in spec 11
- **Backlog**: Tests folder creation → separate session
- **Backlog**: Bug: multi-chat user not added to chat_members

## 2026-01-30 (session 3) — Spec Audit & tzdata Auto-Update
- **Audit**: Verified specs 01-03 against codebase (Ai-driven)
- **Fix**: Renamed `extract_time_strings` → `extract_times` in spec 02
- **Feature**: tzdata auto-update in `main.py`
  - Startup: `update_tzdata()`
  - Background: `tzdata_update_loop()` every 7 days


## 2026-01-30 (session 2) — Fallback UX Improvement
- **Feature**: Fallback now accepts either time OR city retry
- **Spec**: Added fallback sequence diagram to `04_bot_logic.md`
- **Spec**: Updated `06_city_to_timezone.md` fallback description  
- **Code**: Refactored `process_fallback_input` handler
- **UX**: Updated bot messages with ⬆️ REPLY emphasis## 2026-01-30 (session 2) — Fallback UX Improvement

## 2026-01-30 (session 1) — Refactoring & Fallback
- **Refactor**: `get_utc_offset()` moved to `transform.py` (single source)
- **Spec**: Added Mermaid sequence diagram to `04_bot_logic.md` (New User flow)
- **Feature**: Implemented city fallback via system time
  - New FSM state `waiting_for_time`
  - New `get_timezone_by_offset()` in `geo.py`
  - Calculates UTC offset from user's current time

## 2026-01-29 (session 7) — MVP Implementation 🚀
- **Complete**: 9 modules in `src/`, all specs covered
- **Bug Found**: Bot responded to regular message → fixed (reply-only FSM)
- **Bug Found**: Regex captured "22" instead of "22:30" → fixed (finditer)
- **Fix**: Markdown ate underscores in `/tb_help` → removed parse_mode
- **UX**: Add username to conversion format ("Anton: 10:30 Sarajevo...")
- **Gap Fixed**: `/tb_remove` command implemented
- **Gap Fixed**: UTC offset sorting in output
- **Gap Fixed**: @usernames stored in DB, shown in `/tb_members`
- **Audit**: Spec compliance verified against 02-10

**Backlog**:
- If user deletes himself via `/tb_remove` → bot may stuck (FSM state check needed)

## 2026-01-29 (session 6)
- **Added**: 11_implementation_mapping.md
- **Added** Storing flag emoji in DB (to prevent geo calling)

## 2026-01-29 (session 6)
- **Spec**: Created `10_testing_strategy.md` (Unit vs Manual)
- **Tech Stack**: Added `uv` as the official package manager in `01_scope_and_MVP.md`


## 2026-01-29 (session 5)

- **Spec**: Added `09_logging.md` (Levels, Context)
- **Config**: Added `logging.level` to `configuration.yaml`
- **Config**: Moved Regex patterns from `02_capture_logic.md` to `configuration.yaml`


## 2026-01-29 (session 4)
- **Localization**: Converted all bot messages to English in `04`, `06`, `08` specs
- **Docs**: Added Integration Note (Standard API + aiogram) to `04_bot_logic.md`
- **Docs**: Added Technology Stack table to `01_scope_and_MVP.md`
- **Closed questions**:
  - Antiflood handled via config (`cooldown_seconds`)
  - Private chats excluded (MVP = groups only)
- **MVP Readiness: 95%** 


## 2026-01-29 (session 3)
- Added: 08_telegram_commands.md
- Added: Architecture diagrams to all specs (01-05)
- Added: Country flags mapping in 06_city_to_timezone.md
- Updated: Response format with `/tb_help` footer
- Config: added `show_usernames` option
- Cleanup: moved commands from 04_bot_logic.md 08_telegram_commands.md

- **Further:**Re-check gaps, chek messages schema



## 2026-01-29 (session 2)
- Added: `06_city_to_timezone.md` (geocoding + inline buttons)
- Added: `07_response_format.md` (response structure, grouping, day markers)
- Few gaps closed

## 2026-01-29 
- Specs added: `02_capture_logic.md`, `03_transformation_specs.md`, `04_bot_logic.md`, `05_storage.md`
- Gap analysis completed: MVP readiness 70%
- **Further:** Finish specs, close gaps (City→TZ mapping, Response Format)

## 2026-01-27
- Project initialized with directory structure

