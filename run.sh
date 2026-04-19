#!/bin/bash
# run.sh - Simple bot runner with signal propagation

cd "$(dirname "$0")"

# Store PID
BOT_PID=""

cleanup() {
    echo ""
    echo "Received stop signal. Shutting down bot gracefully..."
    kill -TERM $BOT_PID 2>/dev/null
    wait $BOT_PID
    echo "Bot stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting Timezone Bot... (Ctrl+C to stop)"
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

uv run python -m main &
BOT_PID=$!

wait
