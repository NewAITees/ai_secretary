#!/bin/bash
# Lifelog System Launcher

cd "$(dirname "$0")"

echo "Starting Lifelog Activity Collector..."
uv run python -m src.main_collector "$@"
