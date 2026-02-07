## 2026-02-07 (session 4)
- **Code Review**: Comprehensive review of all modules (core, platform adapters, tests)
- **Cleanup**: Removed legacy migration code from `storage/sqlite.py` (~35 lines)
- **Docs**: Updated code review report with findings and recommendations

## 2026-02-07 (session 3)
- **Docs**: Refined `HANDOVER.md` — focus on design decisions with trade-offs (Regex vs LLM, Nominatim, Passive Collection, MemoryStorage)
- **Docs**: Added clickable links to specs in `HANDOVER.md`
- **Docs**: Optimized `README.md` — clearer structure, fixed typo (WhatsApp)
- **Ready for merge** 

## 2026-02-07 (session 2)
- **Translated** all specs to English
**Next Steps** (FOR NEXT SESSIONS):
  - Make time setting messages visible only to the user instead of the entire chat

## 2026-02-07 (session)
- **Fixed** placeholder in discord bot dialog

## 2026-02-06 (session 9)
- **Fixed**: Discord now returns a message after the initial city input. (same logic as in Telegramm)


## 2026-02-06 (session 8)
- **Linter Check** - minor fixes, then PASSED, gitignore update

## 2026-02-06 (session 7)
- **Docs**: Specifications Audit 
- **Docs**: Minor changes in docs and specs.
- **Refactor**: commands.py - extracted part of the code into ui.py

## 2026-02-06 (session 6)
- **Tests**: Added testing for new features.
- **Docs**: Minor changes in HANDOVER.md.


## 2026-02-06 (session 6)
- **Docs**: Сhanges in specifications and documentation. scope_and_MVP.md, HANDOVER.md

## 2026-02-06 (session 6)
- **Logic**: Configured buttons in Discord; testing confirmed this is more intuitive.
- **Docs**: Minor changes in specifications and documentation.
- **Logic**: Verified logic for removing stuck users in Discord; replaced with auto-update.

- **Next Steps** (FOR NEXT SESSIONS):
  - Review specifications.
  - Check for logic gaps.
  - Add test coverage.
  - Clean up and refactor code.

- **Further** (FOR NEXT SESSIONS):
  - Perform manual installation test following README / ONBOARDING.


## 2026-02-05 (session 5)
- **Fixed** - resolved Fallback to time-based timezone detection.
  -Spec city_to_timezone updated
  -Readme.md - Use case added

## 2026-02-05 (session 4) - Stability & Cleanup
- **investigation issue** - Bot hangs on Ctrl+C, and didn't stop properly.
- **Fixed**: `run.sh` now reliably kills both bots on a single Ctrl+C.
- **Next Steps**: 
  Fallback for city-input issue : ask user to input system time - to determine timezone

## 2026-02-05 (session 3) - Discord Integration Research
- **Research**: Analyzed Discord member discovery logic. Unlike Telegram, Discord allows fetching the full member list; evaluating whether to pre-fetch users or maintain reactive registration.
- **Q&A**:
  - Implementation of `force_reply` equivalents and interactive commands in Discord.
  - Risks and benefits of a unified runner for both Telegram and Discord.
  - Logging strategy: balancing unified output with platform-specific debugging needs.
  - Identifying architectural gaps between platform adapters.


- **Code**: Implemented Discord adapter (`src/discord/`), slash commands, event handlers
- **Code**: Created unified launcher (`src/unified_main.py`) — runs both bots via `asyncio.gather()`
- **Updated**: `run.sh`, `configuration.yaml`, `env.example`, `pyproject.toml`

### Thoughts — Member Collection Logic
Discord's user capture logic is different — the entire member list can be retrieved at once (via `guild.members`).

**Decision**: Keep it lazy (consistent with Telegram) — simpler, uniform architecture, and minimizes database load.

### Gaps Between Adapters
- **FSM states**: Discord does not use FSM (parameters are passed directly in slash commands).
- **Cooldown**: Not implemented for Discord (not required for now).
- **Fallback flow**: Discord lacks time-based fallback — only city via parameter.

- **Next Steps**: 
- Resolve open questions, review specifications, and prototype the dual-platform runner.
- [ ] **⚠️ IMPORTANT**: Add signal handler (SIGINT/SIGTERM) to `unified_main.py` for graceful shutdown
  - Current issue: Bot hangs on Ctrl+C because `asyncio.gather()` waits indefinitely for both tasks
  - Discord bot may not close connections properly, causing process to stay in `S+` state
  - Need: Signal handler with timeout to force-stop tasks if graceful shutdown fails
- [ ] Experiment with Discord buttons (optional)
- Tests


## 2026-02-05 (session 2) - Discord introducing
- **Docs**: Spec draft for Discord, minor changes in Scope_and_MVP

## 2026-02-05 (session 1)
- **Docs**: Updated `storage.md` and `HANDOVER.md` with future DB caching architecture.
- **Decision**: Implementation deferred (YAGNI) to maintain simplicity; specifications are documented for future.

## 2026-02-03 (session 11)
- **Refactor**: Eliminated duplicated code in `settings.py` by extracting logic into a helper function (adhering to the DRY principle).

## 2026-02-03 (session 10)
- **Documentation** minor docs markups

## 2026-02-03 (session 9)
- **Fixes**: Address critical logic gaps based on code review:
  - **Middleware**: Added full traceback logging (`exc_info=True`) for DB errors to prevent silent failures.
  - **Logic**: Added validation for missing user timezone in `common.py` (self-healing flow).

## 2026-02-03 (session 8) - docs and specs minor changes
- **Cleanup**: unused imports (`ruff`).
- **Cleanup**: .gitignored few files

## 2026-02-03 (session 7) - docs and specs minor changes
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

