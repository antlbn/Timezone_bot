#!/bin/bash
# run.sh - Simple bot runner with signal propagation

cd "$(dirname "$0")"

# Store PIDs
TG_PID=""
DISCORD_PID=""

cleanup() {
    echo ""
    echo "Received stop signal. Shutting down bots gracefully..."
    kill -TERM $TG_PID $DISCORD_PID 2>/dev/null
    wait $TG_PID $DISCORD_PID
    echo "All bots stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting bots... (Ctrl+C to stop)"

uv run python -m src.main &
TG_PID=$!

uv run python -m src.discord_main &
DISCORD_PID=$!

wait
