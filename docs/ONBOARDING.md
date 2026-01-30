# Onboarding: How to Run the Bot

This guide will help you get the Timezone Bot up and running.

## 🔑 Prerequisites

1.  **Telegram Bot Setup**:
    1.  Open [@BotFather](https://t.me/botfather) in Telegram.
    2.  Send `/newbot` and follow instructions to name your bot.
    3.  **Copy the API Token** provided by BotFather.
    4.  **Configure Privacy** (Critical):
        *   Send `/mybots` -> Select Bot -> `Bot Settings` -> `Group Privacy` -> **Turn off**.
    
2.  **Environment**:
    ```bash
    cp env.example .env
    # Edit .env and paste TELEGRAM_BOT_TOKEN
    ```

---

## 🚀 Manual Execution (Standard)

Requires Python 3.12+.

1.  **Install dependencies**:
    ```bash
    uv sync
    ```
    *(Or `pip install -r requirements.txt`)*

2.  **Run**:
    ```bash
    ./run.sh
    ```

---

## 🧪 Running Tests
```bash
uv run pytest tests/ -v
```

## 🛠️ Configuration
Edit `configuration.yaml`:
- `cooldown_seconds`: Anti-spam delay.
- `capture.patterns`: Regex rules for time extraction.
