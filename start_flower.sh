#!/bin/bash
# Start Flower monitoring interface for Celery

# Determine the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "Starting Flower monitoring interface for BattyCoda..."
celery -A celery_app.celery flower --port=5555