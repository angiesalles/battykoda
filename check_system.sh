#!/bin/bash
# Script to check the health of all BattyCoda system components

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
echo -e "${BLUE}BattyCoda System Health Check${NC}"
echo -e "${BLUE}====================================${NC}"

# Check Redis
echo -e "${YELLOW}► Checking Redis...${NC}"
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✓ Redis is running${NC}"
        # Get Redis info
        REDIS_MEM=$(redis-cli info memory | grep used_memory_human | cut -d: -f2 | tr -d '[:space:]')
        REDIS_CLIENTS=$(redis-cli info clients | grep connected_clients | cut -d: -f2 | tr -d '[:space:]')
        echo -e "  - Memory usage: ${YELLOW}$REDIS_MEM${NC}"
        echo -e "  - Connected clients: ${YELLOW}$REDIS_CLIENTS${NC}"
    else
        echo -e "${RED}✗ Redis is not running${NC}"
    fi
else
    echo -e "${RED}✗ Redis CLI not found${NC}"
fi

# Check Flask app
echo -e "${YELLOW}► Checking Flask app...${NC}"
if [ -f .flask.pid ]; then
    FLASK_PID=$(cat .flask.pid)
    if ps -p $FLASK_PID > /dev/null; then
        echo -e "${GREEN}✓ Flask app is running (PID: $FLASK_PID)${NC}"
        # Get process memory usage
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            FLASK_MEM=$(ps -o rss= -p $FLASK_PID | awk '{print $1/1024 " MB"}')
        else
            # Linux
            FLASK_MEM=$(ps -p $FLASK_PID -o %mem= | tr -d '[:space:]')%
        fi
        echo -e "  - Memory usage: ${YELLOW}$FLASK_MEM${NC}"
    else
        echo -e "${RED}✗ Flask app is not running (PID file exists but process not found)${NC}"
    fi
else
    FLASK_PID=$(ps aux | grep '[p]ython main.py' | awk '{print $2}')
    if [ ! -z "$FLASK_PID" ]; then
        echo -e "${GREEN}✓ Flask app is running (PID: $FLASK_PID)${NC}"
        echo -e "  - (PID file missing, consider restarting with ./refresh_system.sh)"
    else
        echo -e "${RED}✗ Flask app is not running${NC}"
    fi
fi

# Check Celery worker
echo -e "${YELLOW}► Checking Celery worker...${NC}"
CELERY_PIDS=$(pgrep -f "celery -A celery_app.celery worker" || echo "")
if [ ! -z "$CELERY_PIDS" ]; then
    CELERY_COUNT=$(echo "$CELERY_PIDS" | wc -l)
    echo -e "${GREEN}✓ Celery worker is running ($CELERY_COUNT processes)${NC}"
    
    # Check Celery tasks
    if command -v celery &> /dev/null && redis-cli ping &> /dev/null; then
        echo -e "${YELLOW}  ► Checking Celery tasks...${NC}"
        # Use inspect to get task info, redirect stderr to avoid noise
        CELERY_ACTIVE=$(celery -A celery_app.celery inspect active 2>/dev/null || echo "")
        if [ ! -z "$CELERY_ACTIVE" ] && [ "$CELERY_ACTIVE" != "No nodes replied within time constraint." ]; then
            ACTIVE_COUNT=$(echo "$CELERY_ACTIVE" | grep -c ":")
            echo -e "  - Active tasks: ${YELLOW}$ACTIVE_COUNT${NC}"
        else
            echo -e "  - ${RED}Failed to get active task count${NC}"
        fi
    fi
else
    echo -e "${RED}✗ Celery worker is not running${NC}"
fi

# Check Flower
echo -e "${YELLOW}► Checking Flower...${NC}"
FLOWER_PID=$(pgrep -f "celery -A celery_app.celery flower" || echo "")
if [ ! -z "$FLOWER_PID" ]; then
    echo -e "${GREEN}✓ Flower is running (PID: $FLOWER_PID)${NC}"
    echo -e "  - Dashboard URL: ${YELLOW}http://localhost:5555${NC}"
else
    echo -e "${RED}✗ Flower is not running${NC}"
fi

# Check network connectivity (to Redis)
echo -e "${YELLOW}► Checking network connectivity...${NC}"
if command -v nc &> /dev/null; then
    if nc -z localhost 6379; then
        echo -e "${GREEN}✓ Redis port is reachable${NC}"
    else
        echo -e "${RED}✗ Redis port is not reachable${NC}"
    fi
    
    if nc -z localhost 8060; then
        echo -e "${GREEN}✓ Flask port is reachable${NC}"
    else
        echo -e "${RED}✗ Flask port is not reachable${NC}"
    fi
    
    if nc -z localhost 5555; then
        echo -e "${GREEN}✓ Flower port is reachable${NC}"
    else
        echo -e "${RED}✗ Flower port is not reachable${NC}"
    fi
else
    echo -e "${YELLOW}► Network check skipped (nc command not available)${NC}"
fi

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}System Health Check Complete${NC}"
echo -e "${BLUE}====================================${NC}"