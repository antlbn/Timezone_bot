# Timezone Bot Handover & Documentation

Welcome to the Timezone Bot project. This bot is designed for distributed teams to automatically handle time conversions in Telegram group chats.

## 🚀 Quick Start (Local Run)

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (Recommended) or `pip`

### Setup
1. **Clone & Install**:
   ```bash
   git clone <repo_url>
   cd Timezone_bot
   uv sync  # or pip install -r requirements.txt
   ```
2. **Environment**:
   Copy `env.example` to `.env` and add your `TELEGRAM_BOT_TOKEN`.
3. **Run**:
   ```bash
   ./run.sh
   # This script handles db init and bot startup
   ```

---

## 🏗️ Project Structure
- `src/`: Core logic (AI-assisted implementation).
- `tests/`: 47 automated unit and integration tests.
- `journal/`: Process journal and specs.
- `configuration.yaml`: User-friendly bot settings.
