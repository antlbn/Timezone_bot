#!/bin/bash
# Run the timezone bot
cd "$(dirname "$0")"
uv run python -m src.main
