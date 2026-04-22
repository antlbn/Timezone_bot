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

    - `TELEGRAM_BOT_TOKEN` for Telegram runtime
    - `DISCORD_BOT_TOKEN` for Discord runtime
    - `LLM_API_KEY` for the primary LLM provider
    - `LLM_FALLBACK_API_KEY` for the optional fallback provider
    - `LLM_BASE_URL` *(optional)* — override the primary endpoint without editing `configuration.yaml`
    - `LLM_FALLBACK_BASE_URL` *(optional)* — override the fallback endpoint without editing `configuration.yaml`

    Current default LLM runtime:

    - primary model: Gemini 3.1 Flash-Lite via its OpenAI-compatible endpoint
    - fallback model: for instance llama 8b / Nemotron 4 12B  / gpt 20b
    - the current prompt contract also works well with Nemotron and smaller models in the Llama 8B class

    Notes:

    - the LLM env names are intentionally provider-agnostic,
    - the canonical LLM contract is exactly two endpoints and two keys: primary + fallback,

> [!TIP]
> **Startup Logic**: Each bot checks its own token. If `TELEGRAM_BOT_TOKEN` is set — Telegram bot starts. If `DISCORD_BOT_TOKEN` is set — Discord bot starts. Missing token = bot skips gracefully (no crash). You can run one or both.

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
| `bot.response_style` | `inline_sentence` | Reply layout. `block` — one timezone per line with flags and optional names; `inline_sentence` — compact flag-free inline rows. |
| `bot.reply_to_original_message` | `false` | Post the conversion as a thread reply to the triggering message. |
| `bot.settings_cleanup_timeout_seconds` | `30` | Auto-delete TTL (in seconds) for short-lived bot messages (`/tb_help`, timezone prompts, etc.) in shared chats. Set `0` to disable. |

> [!TIP]
> `show_event_title` reads what the LLM returned — it never invents a title. Turning it `off` suppresses all titles regardless of LLM output.
> `show_usernames` affects `block` replies only. `inline_sentence` stays compact and does not show flags or member names.

#### 🎨 Formatting Showcase

By tweaking `configuration.yaml`, you can radically change how the bot looks in chat.

**Option A: Clean and Compact (Default)**
*(Settings: `response_style: inline_sentence`)*
```text
👤 Maria: Let's sync tomorrow at 3pm

🤖 It is 15:00 Berlin, 09:00 New York
```

**Option A2: Compact with Event Titles**
*(Settings: `response_style: inline_sentence`, `show_event_title: true`)*
```text
👤 Jane: Standup at 10:30, then retro at 15:00.

🤖 standup
   It is 10:30 London, 11:30 Berlin

   retro
   It is 15:00 London, 16:00 Berlin
```

**Option B: Detailed Block with Usernames and Context**
*(Settings: `response_style: block`, `show_usernames: true`, `show_event_title: true`)*
```text
👤 Anton: The final release review is postponed to tomorrow 5pm due to testing updates.

🤖 final release review
   17:00 Berlin 🇩🇪 @anton, @maria
   09:00 New York 🇺🇸 @jane
```

---

### `llm` — Detection Model

| Key | Default | Description |
| :--- | :--- | :--- |
| `llm.model` | `gemini-3.1-flash-lite-preview` | Primary model identifier. |
| `llm.temperature` | `0.1` | Low temperature keeps detection deterministic. |
| `llm.base_url` | Gemini OpenAI-compat endpoint | Default primary endpoint. Override via `.env` with `LLM_BASE_URL`. |
| `llm.api_key_env` | `LLM_API_KEY` | Name of the env var holding the primary provider key. |
| `llm.fallback.enabled` | `true` | Enable automatic retry on the fallback model when the primary fails. |
| `llm.fallback.model` | `llama-3.1-8b-instant` | Fallback model identifier. |
| `llm.fallback.base_url` | Groq OpenAI-compat endpoint | Default fallback endpoint. Override via `.env` with `LLM_FALLBACK_BASE_URL`. |
| `llm.fallback.api_key_env` | `LLM_FALLBACK_API_KEY` | Name of the env var holding the fallback provider key. |

---

### `event_detection` — LLM Pipeline Guards

| Key | Default | Description |
| :--- | :--- | :--- |
| `event_detection.onboarding_timeout_seconds` | `120` | How long a frozen message waits for onboarding to complete before being discarded. Cleanup runs on a 60-second loop, so the effective discard point may lag by up to about 60 seconds. |
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
