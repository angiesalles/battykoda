#!/bin/bash
# Start a Celery worker for BattyCoda

# Set up colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Determine the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Create logs directory if it doesn't exist
mkdir -p logs

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Starting Celery Worker${NC}"
echo -e "${BLUE}====================================${NC}"

# Clear the log file
> logs/celery_worker.log

echo -e "${YELLOW}► Starting Celery worker...${NC}"
echo -e "${YELLOW}► Log file: logs/celery_worker.log${NC}"
echo -e "${YELLOW}► Press Ctrl+C to stop${NC}"

# Start Celery worker in foreground mode for easy debugging
celery -A celery_app.celery worker --loglevel=info --logfile=logs/celery_worker.log

# Note: This script starts Celery in the foreground for debugging
# Use start_system.sh to start all components in the background