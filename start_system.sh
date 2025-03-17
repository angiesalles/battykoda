#!/bin/bash
# Master script to start the entire BattyCoda system
# This starts Redis, Celery worker, Flower, and the Flask app

# Set up colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Set up error handling
set -e
trap 'echo -e "${RED}An error occurred. Exiting...${NC}"; exit 1' ERR

# Determine the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Create logs directory if it doesn't exist
mkdir -p logs

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Starting BattyCoda System${NC}"
echo -e "${BLUE}====================================${NC}"

# Check if Redis is running
echo -e "${YELLOW}Checking Redis status...${NC}"
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✓ Redis is already running${NC}"
    else
        echo -e "${YELLOW}► Starting Redis...${NC}"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            brew services start redis || { echo -e "${RED}Failed to start Redis${NC}"; exit 1; }
        else
            # Linux
            sudo systemctl start redis-server || { echo -e "${RED}Failed to start Redis${NC}"; exit 1; }
        fi
        echo -e "${GREEN}✓ Redis started${NC}"
    fi
else
    echo -e "${RED}⚠ Redis CLI not found. Please install Redis first.${NC}"
    echo -e "${YELLOW}On macOS: brew install redis${NC}"
    echo -e "${YELLOW}On Linux: sudo apt install redis-server${NC}"
    exit 1
fi

# Start Celery worker in background
echo -e "${YELLOW}► Starting Celery worker...${NC}"
celery -A celery_app.celery worker --loglevel=info --detach --logfile=logs/celery_worker.log || { echo -e "${RED}Failed to start Celery worker${NC}"; exit 1; }
echo -e "${GREEN}✓ Celery worker started${NC}"

# Start Flower in background
echo -e "${YELLOW}► Starting Flower monitoring...${NC}"
celery -A celery_app.celery flower --port=5555 --detach --logfile=logs/flower.log || { echo -e "${RED}Failed to start Flower${NC}"; exit 1; }
echo -e "${GREEN}✓ Flower started at http://localhost:5555${NC}"

# Start Flask app
echo -e "${YELLOW}► Starting Flask application...${NC}"
python main.py > logs/flask_app.log 2>&1 &
FLASK_PID=$!
echo $FLASK_PID > .flask.pid
echo -e "${GREEN}✓ Flask app started at http://localhost:8060 (PID: $FLASK_PID)${NC}"

echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}✓ All systems started successfully!${NC}"
echo -e "${BLUE}====================================${NC}"
echo -e "Flask app: ${GREEN}http://localhost:8060${NC}"
echo -e "Flower dashboard: ${GREEN}http://localhost:5555${NC}"
echo -e "Log files are in: ${YELLOW}${SCRIPT_DIR}/logs${NC}"
echo -e "To stop the system, run: ${YELLOW}./stop_system.sh${NC}"