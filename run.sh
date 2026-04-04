#!/bin/bash
# run.sh - Simple bot runner with signal propagation

cd "$(dirname "$0")"

ENV_FILE=".env"

# Store PIDs
TG_PID=""
DISCORD_PID=""

get_env_value() {
    local key="$1"
    local value
    value=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -n 1 | cut -d '=' -f 2-)
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    printf '%s' "$value"
}

cleanup() {
    echo ""
    echo "Received stop signal. Shutting down bots gracefully..."
    [ -n "$TG_PID" ] && kill -TERM "$TG_PID" 2>/dev/null
    [ -n "$DISCORD_PID" ] && kill -TERM "$DISCORD_PID" 2>/dev/null
    [ -n "$TG_PID" ] && wait "$TG_PID"
    [ -n "$DISCORD_PID" ] && wait "$DISCORD_PID"
    echo "All bots stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE not found."
    echo "Create it first, for example: cp env.example .env"
    exit 1
fi

TELEGRAM_TOKEN_VALUE=$(get_env_value "TELEGRAM_TOKEN")
DISCORD_TOKEN_VALUE=$(get_env_value "DISCORD_TOKEN")

if [ -z "$TELEGRAM_TOKEN_VALUE" ] && [ -z "$DISCORD_TOKEN_VALUE" ]; then
    echo "Error: neither TELEGRAM_TOKEN nor DISCORD_TOKEN is set in $ENV_FILE."
    echo "Set at least one platform token before запуском бота."
    exit 1
fi

echo "Starting bots... (Ctrl+C to stop)"

if [ -n "$TELEGRAM_TOKEN_VALUE" ]; then
    # Ignore any unrelated active virtualenv. `uv` should resolve this project from its own `.venv`.
    env -u VIRTUAL_ENV uv run python -m src.main &
    TG_PID=$!
fi

if [ -n "$DISCORD_TOKEN_VALUE" ]; then
    env -u VIRTUAL_ENV uv run python -m src.discord_main &
    DISCORD_PID=$!
fi

wait
