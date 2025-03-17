#!/bin/bash
# Start a Celery worker for BattyCoda

# Determine the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "Starting Celery worker for BattyCoda..."
celery -A celery_app.celery worker --loglevel=info