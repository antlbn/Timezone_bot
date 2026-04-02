# Onboarding: How to Run the Bot

This guide covers the current MVP local setup.

## Clone Repository

```bash
git clone https://github.com/antlbn/Timezone_bot.git
cd Timezone_bot
```

## Prerequisites

1.  **Telegram Bot Setup**:
    1.  Open [@BotFather](https://t.me/botfather) in Telegram.
    2.  Send `/newbot` and follow instructions to name your bot.
    3.  **Copy the API Token** provided by BotFather.
    4.  **Configure Privacy** (Critical):
        *   Send `/mybots` -> Select Bot -> `Bot Settings` -> `Group Privacy` -> **Turn off**.

2.  **Discord Bot Setup** (optional):
    1.  [Discord Developer Portal](https://discord.com/developers/applications) → New Application → Bot → Copy **Token**.
    2.  **Privileged Gateway Intents** (scroll down in Bot section):
        - ✅ Server Members Intent
        - ✅ Message Content Intent
        - Save Changes.
    3.  **OAuth2 → URL Generator**:
        - Scopes: `bot`, `applications.commands`
        - Permissions: `Send Messages`, `Read Message History`, `Use Slash Commands`
        - Copy Generated URL → open in browser → select server.
    
3.  **Environment**:
    ```bash
    cp env.example .env
    ```

    Add these values to `.env`:

    - `TELEGRAM_TOKEN` for Telegram runtime
    - `DISCORD_TOKEN` for Discord runtime
    - `LLM_API_KEY` for the primary LLM provider
    - `LLM_FALLBACK_API_KEY` for the optional fallback provider

    Current default LLM runtime:

    - primary model: Gemini 3.0 Flash-Lite via its OpenAI-compatible endpoint
    - fallback model: llama 8b  via Groq its OpenAI-compatible endpoint
    - the current prompt contract also works well with Nemotron and smaller models in the Llama 8B class

    Notes:

    - the env names are intentionally provider-agnostic,
    - `LLM_API_KEY` and `LLM_FALLBACK_API_KEY` are the preferred names,

> [!TIP]
> **Startup Logic**: Each bot checks its own token. If `TELEGRAM_TOKEN` is set — Telegram bot starts. If `DISCORD_TOKEN` is set — Discord bot starts. Missing token = bot skips gracefully (no crash). You can run one or both.

---

## Manual Execution

Requires Python 3.12+.

1.  **Install dependencies**:
    ```bash
    uv sync
    ```

2.  **Run**:
    ```bash
    ./run.sh
    ```
    
---

## Running Tests
```bash
uv run pytest tests/ -v
```

---

## Runtime Behavior

Once the bot is running:

1.  Add it to a Telegram group or Discord server.
2.  No global setup command is required for normal conversion flow.
3.  Detection is LLM-only in the canonical MVP flow.
4.  Onboarding is lazy:
    - if a configured user mentions a time, the bot converts immediately,
    - if an unconfigured user mentions a time, the bot starts onboarding and freezes that message,
    - after successful setup, the frozen message is replayed.

---

## Configuration

Runtime behavior is configured via `configuration.yaml`.

| Setting | Type | Description |
| :--- | :--- | :--- |
| `logging.level` | `DEBUG`/`INFO` | Verbosity of logs. |
| `bot.show_usernames` | Boolean | If `true`, adds names: *"17:00 London" @AntonLubny*. |
| `bot.show_event_title` | Boolean | Show `event_title` when the detector returns it. |
| `bot.reply_to_original_message` | Boolean | Send conversion as a direct reply to the source message. |
| `bot.settings_cleanup_timeout_seconds` | Integer | Auto-delete short-lived setup/help noise in shared chats. |
| `llm.model` | String | Primary detection model. |
| `llm.base_url` | String | OpenAI-compatible endpoint for the primary provider. |
| `llm.api_key_env` | String | Env var name for the primary provider key. |
| `llm.fallback.*` | Section | Optional fallback provider/model settings. |
| `event_detection.onboarding_timeout_seconds` | Integer | How long frozen messages wait during onboarding. |
| `event_detection.dm_onboarding_cooldown_seconds` | Integer | Cooldown before re-inviting ignored users. |
| `event_detection.max_message_age_seconds` | Integer | Skip stale messages after downtime/restart. |
| `event_detection.max_message_hard_skip_chars` | Integer | Hard length guard for oversized messages. |

Canonical config details live in [journal/13_configuration.md](../journal/13_configuration.md).
