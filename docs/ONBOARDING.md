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

Runtime behavior is configured via `configuration.yaml`. All sections and their defaults are described below.

---

### `logging` — Observability

| Key | Default | Description |
| :--- | :--- | :--- |
| `logging.level` | `DEBUG` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `logging.format` | `text` | Output format: `text` (human-readable) or `json` (structured). |

---

### `bot` — Output and UX

| Key | Default | Description |
| :--- | :--- | :--- |
| `bot.show_usernames` | `false` | Append names to each timezone row: `13:00 Berlin 🇩🇪 @alice, Bob`. |
| `bot.show_event_title` | `true` | Show `event_title` above a block when the LLM explicitly extracted it. If `false`, titles are always suppressed. |
| `bot.response_style` | `inline_sentence` | Reply layout. `block` — one timezone per line; `inline_sentence` — compact single-line format. |
| `bot.reply_to_original_message` | `false` | Post the conversion as a thread reply to the triggering message. |
| `bot.settings_cleanup_timeout_seconds` | `30` | Auto-delete TTL (in seconds) for short-lived bot messages (`/tb_help`, timezone prompts, etc.) in shared chats. Set `0` to disable. |

> [!TIP]
> `show_event_title` reads what the LLM returned — it never invents a title. Turning it `off` suppresses all titles regardless of LLM output.

---

### `llm` — Detection Model

| Key | Default | Description |
| :--- | :--- | :--- |
| `llm.model` | `gemini-2.0-flash-lite` | Primary model identifier. |
| `llm.temperature` | `0.1` | Low temperature keeps detection deterministic. |
| `llm.base_url` | Gemini OpenAI-compat endpoint | Any OpenAI-compatible endpoint. Swap to use a different provider. |
| `llm.api_key_env` | `LLM_API_KEY` | Name of the env var holding the primary provider key. |
| `llm.fallback.enabled` | `true` | Enable automatic retry on the fallback model when the primary fails. |
| `llm.fallback.model` | `llama-3.1-8b-instant` | Fallback model identifier. |
| `llm.fallback.base_url` | Groq OpenAI-compat endpoint | Fallback provider endpoint. |
| `llm.fallback.api_key_env` | `LLM_FALLBACK_API_KEY` | Name of the env var holding the fallback provider key. |

---

### `event_detection` — LLM Pipeline Guards

| Key | Default | Description |
| :--- | :--- | :--- |
| `event_detection.onboarding_timeout_seconds` | `120` | How long a frozen message waits for onboarding to complete before being discarded. |
| `event_detection.dm_onboarding_cooldown_seconds` | `600` | Minimum gap before re-prompting a user who ignored or abandoned the onboarding DM. |
| `event_detection.max_message_age_seconds` | `30` | Messages older than this are skipped — prevents stale replies after restart or downtime. |
| `event_detection.max_message_hard_skip_chars` | `2000` | Hard safety ceiling: messages longer than this are never sent to the LLM. |
| `event_detection.log_prompts` | `false` | If `true`, prints the full LLM prompt to the console. Useful for debugging detection failures. |

---

### `storage` — Data Management

| Key | Default | Description |
| :--- | :--- | :--- |
| `storage.inactive_user_retention_days` | `30` | Remove users who haven't interacted with the bot for this many days. Set `0` to disable pruning. |

---

Canonical config reference: [journal/13_configuration.md](../journal/13_configuration.md).
