# Onboarding: How to Run the Bot

This guide will help you get the Timezone Bot up and running.

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
    # Edit .env and paste TELEGRAM_TOKEN and/or DISCORD_TOKEN
    ```

> [!TIP]
> **Startup Logic**: Each bot checks its own token. If `TELEGRAM_TOKEN` is set — Telegram bot starts. If `DISCORD_TOKEN` is set — Discord bot starts. Missing token = bot skips gracefully (no crash). You can run one or both.

---

## Manual Execution (Standard)

Requires Python 3.12+.

1.  **Install dependencies**:
    ```bash
    uv sync
    ```

2.  **Run** (both Telegram and Discord bots together):
    ```bash
    ./run.sh
    ```
    
---

## Running Tests
```bash
uv run pytest tests/ -v
```

---

## plug-and-play Usage


Once the bot is running:
1.  **Add the bot** to any Telegram group or Discord channel.
2.  **No setup required**: You don't need to send `/start` or any configuration commands.
3.  **Zero-Friction Onboarding**: When an unregistered user sends **any** message to the chat, the bot immediately triggers the onboarding flow and **saves (buffers)** that message. Once the user sets their city, the bot automatically processes the buffered message and replies to it.
4.  **LLM-Powered Detection**: The bot uses an LLM to understand natural language time mentions and extracted events, ensuring high accuracy without complex regex configuration.

---

## 🛠️ Configuration

The bot is configurable via `configuration.yaml`.

| Setting | Type | Description |
| :--- | :--- | :--- |
| `logging.level` | `DEBUG`/`INFO` | Verbosity of logs. |
| `bot.display_limit_per_chat` | Integer | Max timezones to show (0 = no limit). |
| `bot.time_format` | String | Output format: `"24h"` (17:00) or `"12h"` (5:00 PM). |
| `bot.show_usernames` | Boolean | If `true`, adds names: *"17:00 London" @AntonLubny*. |
| `bot.cooldown_seconds` | Integer | Anti-spam delay. 0 = disabled. |
| `bot.max_message_age_seconds` | Integer | Max age (seconds) for messages in queue before they are considered stale (default 20). |
| `llm.model` | String | Model used for event detection (e.g., `gpt-4o`, `llama-3`). |
