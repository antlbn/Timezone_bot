#!/bin/bash
# Run the timezone bot (Telegram + Discord) as separate processes
# Ctrl+C stops both

cd "$(dirname "$0")"

# Trap Ctrl+C to kill all background jobs
trap 'echo "Stopping bots..."; kill $(jobs -p) 2>/dev/null; exit 0' SIGINT SIGTERM

echo "Starting bots... (Ctrl+C to stop)"

# Start Telegram bot in background
uv run python -m src.main &
TG_PID=$!

# Start Discord bot in background  
uv run python -m src.discord_main &
DISCORD_PID=$!

# Wait for any to exit
wait
