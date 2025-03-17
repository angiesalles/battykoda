#!/bin/bash
# Start Flower monitoring dashboard for BattyCoda

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
echo -e "${BLUE}Starting Flower Monitoring Dashboard${NC}"
echo -e "${BLUE}====================================${NC}"

# Clear log file
> logs/flower.log

echo -e "${YELLOW}► Starting Flower dashboard...${NC}"
echo -e "${YELLOW}► Dashboard URL: http://localhost:5555${NC}"
echo -e "${YELLOW}► Log file: logs/flower.log${NC}"
echo -e "${YELLOW}► Press Ctrl+C to stop${NC}"

# Start Flower in foreground mode for easy debugging
celery -A celery_app.celery flower --port=5555 --logfile=logs/flower.log

# Note: This script starts Flower in the foreground for debugging
# Use start_system.sh to start all components in the background