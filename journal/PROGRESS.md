# Progress Journal
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

