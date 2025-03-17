#!/bin/bash
# Script to stop the entire BattyCoda system

# Set up colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Determine the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Stopping BattyCoda System${NC}"
echo -e "${BLUE}====================================${NC}"

# Stop Flask app
if [ -f .flask.pid ]; then
    FLASK_PID=$(cat .flask.pid)
    if ps -p $FLASK_PID > /dev/null; then
        echo -e "${YELLOW}► Stopping Flask app (PID: $FLASK_PID)...${NC}"
        kill $FLASK_PID
        rm .flask.pid
        echo -e "${GREEN}✓ Flask app stopped${NC}"
    else
        echo -e "${YELLOW}► Flask app not running (PID: $FLASK_PID not found)${NC}"
        rm .flask.pid
    fi
else
    echo -e "${YELLOW}► Flask PID file not found, attempting to find and kill...${NC}"
    FLASK_PID=$(ps aux | grep '[p]ython main.py' | awk '{print $2}')
    if [ ! -z "$FLASK_PID" ]; then
        echo -e "${YELLOW}► Found Flask app with PID: $FLASK_PID. Stopping...${NC}"
        kill $FLASK_PID
        echo -e "${GREEN}✓ Flask app stopped${NC}"
    else
        echo -e "${YELLOW}► No Flask app process found${NC}"
    fi
fi

# Stop Celery worker
echo -e "${YELLOW}► Stopping Celery workers...${NC}"
pkill -f "celery -A celery_app.celery worker" || echo -e "${YELLOW}► No Celery workers found${NC}"
echo -e "${GREEN}✓ Celery workers stopped${NC}"

# Stop Flower
echo -e "${YELLOW}► Stopping Flower...${NC}"
pkill -f "celery -A celery_app.celery flower" || echo -e "${YELLOW}► No Flower process found${NC}"
echo -e "${GREEN}✓ Flower stopped${NC}"

# Stop Redis (optional)
if [ "$1" == "--stop-redis" ]; then
    echo -e "${YELLOW}► Stopping Redis...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew services stop redis || echo -e "${RED}Failed to stop Redis${NC}"
    else
        # Linux
        sudo systemctl stop redis-server || echo -e "${RED}Failed to stop Redis${NC}"
    fi
    echo -e "${GREEN}✓ Redis stopped${NC}"
else
    echo -e "${YELLOW}► Leaving Redis running (use --stop-redis to stop it)${NC}"
fi

echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}✓ All systems stopped successfully!${NC}"
echo -e "${BLUE}====================================${NC}"