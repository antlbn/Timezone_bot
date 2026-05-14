# Setup

This document describes the current local setup and the runtime configuration that is actually wired into the code.

## Prerequisites

- Python 3.12+
- `uv`
- Telegram bot token if you want to run the Telegram adapter
- Discord bot token if you want to run the Discord adapter
- LLM API key for detection

## Telegram Bot

1. Open [@BotFather](https://t.me/botfather) in Telegram.
2. Create a bot with `/newbot`.
3. Copy the token into `.env`.
4. Disable group privacy for the bot:
   `Bot Settings -> Group Privacy -> Turn off`

## Discord Bot

1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a bot and copy the token into `.env`.
3. Enable privileged intents:
   `Server Members Intent`
   `Message Content Intent`
4. Add the bot to a server with scopes `bot` and `applications.commands`.

## Environment Variables

Create `.env` from the example file:

```bash
cp env.example .env
```

Supported variables:

- `TELEGRAM_BOT_TOKEN`
- `DISCORD_BOT_TOKEN`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_TEMPERATURE`
- `LLM_FALLBACK_API_KEY`
- `LLM_FALLBACK_BASE_URL`
- `LLM_FALLBACK_MODEL`
- `LLM_FALLBACK_TEMPERATURE`

LLM settings are resolved as:

- environment variables are the source of truth
- if a variable is missing, the code falls back to its built-in default

Fallback is enabled only when both of these are true:

- `LLM_FALLBACK_API_KEY` is present in the environment
- fallback model settings are present or can use built-in defaults

## Install And Run

Install dependencies:

```bash
uv sync
```

Run the bot:

```bash
./run.sh
```

## Tests

```bash
uv run pytest tests/ -v
```

## Active Configuration

The current code reads these keys from `configuration.yaml`.

### `logging`

| Key | Default | Used For |
|---|---|---|
| `logging.level` | `DEBUG` in repo config | Python logging level in `main.py` |

### `bot`

| Key | Default | Used For |
|---|---|---|
| `bot.show_usernames` | `true` | Show member names in block formatting |
| `bot.show_event_title` | `true` | Show extracted event title when available |
| `bot.response_style` | `inline_sentence` | Reply layout |
| `bot.max_age_fresh_secs` | `30` | Drop stale fresh messages |
| `bot.onboarding_cooldown_secs` | `600` | Cooldown before showing onboarding again |
| `bot.onboarding_pending_ttl_secs` | `120` | TTL for stored pending onboarding messages |
| `bot.group_auto_delete_delay_secs` | `20` | Telegram message auto-delete delay |

### `event_detection`

| Key | Default | Used For |
|---|---|---|
| `event_detection.log_prompts` | `false` | Log full LLM prompt and user payload |
| `event_detection.max_message_hard_skip_chars` | `2000` | Hard message-length limit before LLM detection |

## Runtime Notes

- The LLM sees only the current message.
- LLM credentials and model settings are configured through `.env`.
- If a user without a timezone mentions time, the bot stores the latest pending message for that chat and starts onboarding.
- After successful onboarding, pending messages for that user may be replayed across chats if they are still present in pending storage.
- Known members are discovered from observed chat activity; the bot does not load full member lists proactively.
