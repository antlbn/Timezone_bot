#!/bin/bash
# Run the timezone bot (Telegram + Discord)
cd "$(dirname "$0")"
uv run python -m src.unified_main
