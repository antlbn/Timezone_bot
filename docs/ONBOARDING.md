# Onboarding

This guide explains how to run the bot locally and what must be present in `.env`.

## Clone Repository

```bash
git clone https://github.com/antlbn/Timezone_bot.git
cd Timezone_bot
```

## Prerequisites

- Python 3.12+
- `uv`
- at least one platform token: Telegram or Discord
- one LLM provider reachable through an OpenAI-compatible API

## Environment

```bash
cp env.example .env
```

Then fill the fields you need.

### Required platform fields

Set one or both:

```dotenv
TELEGRAM_TOKEN=
DISCORD_TOKEN=
```

Startup logic:
- if `TELEGRAM_TOKEN` is set, the Telegram bot starts
- if `DISCORD_TOKEN` is set, the Discord bot starts
- if one token is missing, that platform is skipped without crashing

### Required LLM fields

Main configuration is model-agnostic:

```dotenv
LLM_MODEL=
LLM_BASE_URL=
LLM_API_KEY=
```

Meaning:
- `LLM_MODEL`: model name passed into the client
- `LLM_BASE_URL`: OpenAI-compatible endpoint
- `LLM_API_KEY`: API key for that endpoint

The code also supports an optional model-agnostic fallback key:

```dotenv
LLM_FALLBACK_API_KEY=
```

This is optional and only used when `LLM_API_KEY` is not set.

### Optional LangSmith fields

Useful for tracing and evals:

```dotenv
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=timezone-bot-tests
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

If LangSmith is not needed, these can stay empty.

## Platform Setup

### Telegram Bot Setup

1. Open [@BotFather](https://t.me/botfather).
2. Create a bot and copy the token into `TELEGRAM_TOKEN`.
3. Disable group privacy if the bot should read normal group messages in groups.

### Discord Bot Setup

1. Open the Discord Developer Portal and create an application.
2. Create a bot and copy the token into `DISCORD_TOKEN`.
3. Enable privileged intents:
   - `Server Members Intent`
   - `Message Content Intent`
4. Invite the bot with scopes:
   - `bot`
   - `applications.commands`

## Install Dependencies

```bash
uv sync
```

## Run

Run both entrypoints together:

```bash
./run.sh
```

Or run platforms separately:

```bash
uv run python -m src.main
uv run python -m src.discord_main
```

## Running Tests

```bash
uv run pytest
```

Run tests with coverage:

```bash
uv run pytest --cov=src --cov-report=term-missing
```

## Plug-and-Play Usage

Once the bot is running:

1. Add it to a Telegram group or Discord server/channel.
2. Users chat normally, without a conversion command.
3. If a user is not registered yet, the bot may offer onboarding when it sees an actionable message.
4. After the user sets their city/timezone, future time mentions are converted automatically.

Important current behavior:
- the first actionable message is not buffered
- old actionable messages are not replayed after onboarding

## Configuration

Main runtime settings live in `configuration.yaml`.

### Logging

| Setting | Description |
|---|---|
| `logging.level` | Log verbosity |

### Bot Output and UX

| Setting | Description |
|---|---|
| `bot.render_mode` | Reply layout: `compact_inline` or `vertical` |
| `bot.compact_inline_code_block` | Wrap `compact_inline` replies in a code block |
| `bot.show_sender_prefix` | Prefix the reply with the sender display name |
| `bot.display_limit_per_chat` | Max number of displayed timezones/users |
| `bot.time_format` | `24h` or `12h` output |
| `bot.show_usernames` | Whether to include usernames in replies |
| `bot.cooldown_seconds` | Anti-spam cooldown |
| `bot.settings_cleanup_timeout_seconds` | Auto-cleanup timeout for settings UI |

### Reply Layout Examples

Basic inline layout:

```yaml
bot:
  render_mode: compact_inline
  compact_inline_code_block: false
  show_sender_prefix: false
```

Example output:

```text
deadline | 08:00 London, 09:00 Vienna, 03:00 New York
```

Vertical layout:

```yaml
bot:
  render_mode: vertical
  show_sender_prefix: false
```

Example output:

```text
deadline
8:00 London 🇬🇧
09:00 Vienna 🇦🇹
03:00 New York 🇺🇸
```

### Event Detection Context and Limits

| Setting | Description |
|---|---|
| `event_detection.context_messages` | Number of recent human messages passed into LLM context |
| `event_detection.max_tokens` | Prompt token budget cap |
| `event_detection.max_message_length_chars` | Soft truncation limit per message before prompt assembly |
| `event_detection.max_message_age_seconds` | Stale-message protection |
| `event_detection.max_message_hard_skip_chars` | Hard skip threshold for very long messages |

### Event Detection Behavior

| Setting | Description |
|---|---|
| `event_detection.temperature` | LLM temperature |
| `event_detection.edit_in_place` | Whether edits update an existing bot reply instead of republishing |
| `event_detection.republish_edited_message_after_distance` | Distance threshold for republishing instead of silent edit |
| `event_detection.dm_onboarding_cooldown_seconds` | Delay before offering onboarding again in DM |
