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

# Check R prediction servers (if available)
echo -e "${YELLOW}► Checking R prediction servers...${NC}"

# Check the direct KNN server (port 8000)
echo -e "${YELLOW}  ► Checking direct KNN R server (port 8000)...${NC}"
DIRECT_SERVER_RUNNING=false

# Method 1: Check PID file for direct server
if [ -f .r_server_direct.pid ]; then
    R_SERVER_PID=$(cat .r_server_direct.pid)
    if ps -p $R_SERVER_PID > /dev/null; then
        echo -e "${GREEN}✓ Direct KNN R server is running (PID: $R_SERVER_PID)${NC}"
        DIRECT_SERVER_RUNNING=true
        
        # Try to ping the server API
        if command -v curl &> /dev/null; then
            R_SERVER_PING=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ping 2>/dev/null || echo "failed")
            if [ "$R_SERVER_PING" == "200" ]; then
                echo -e "  - API is responsive (ping: 200 OK)"
                
                # Get more details about the server
                if command -v curl &> /dev/null && command -v jq &> /dev/null; then
                    R_SERVER_INFO=$(curl -s http://localhost:8000/ping 2>/dev/null | jq -r 2>/dev/null || echo "{}")
                    echo -e "  - Server info: ${YELLOW}$R_SERVER_INFO${NC}"
                fi
            else
                echo -e "  - ${RED}API is not responsive (ping: $R_SERVER_PING)${NC}"
            fi
        fi
    else
        echo -e "${RED}✗ Direct KNN R server is not running (PID file exists but process not found)${NC}"
        rm -f .r_server_direct.pid
    fi
fi

# Method 2: Check port 8000
if [ "$DIRECT_SERVER_RUNNING" = false ]; then
    PORT_8000_PID=$(lsof -ti :8000 2>/dev/null)
    if [ ! -z "$PORT_8000_PID" ]; then
        # Check if it's RStudio
        if ps -p $PORT_8000_PID -o command | grep -qi "RStudio"; then
            echo -e "${YELLOW}✓ RStudio session is using port 8000 (PID: $PORT_8000_PID)${NC}"
        else
            echo -e "${GREEN}✓ Direct KNN R server is running on port 8000 (PID: $PORT_8000_PID)${NC}"
            echo -e "  - (PID file missing, consider restarting with ./start_system.sh)"
            DIRECT_SERVER_RUNNING=true
        fi
    else
        echo -e "${YELLOW}  -> Direct KNN R server is not running${NC}"
    fi
fi

# Also check for alternative port (8002)
PORT_8002_PID=$(lsof -ti :8002 2>/dev/null)
if [ ! -z "$PORT_8002_PID" ] && [ "$DIRECT_SERVER_RUNNING" = false ]; then
    echo -e "${GREEN}✓ Direct KNN R server is running on alternative port 8002 (PID: $PORT_8002_PID)${NC}"
    DIRECT_SERVER_RUNNING=true
    
    # Try to ping the server API
    if command -v curl &> /dev/null; then
        R_SERVER_PING=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/ping 2>/dev/null || echo "failed")
        if [ "$R_SERVER_PING" == "200" ]; then
            echo -e "  - API is responsive (ping: 200 OK)"
        else
            echo -e "  - ${RED}API is not responsive (ping: $R_SERVER_PING)${NC}"
        fi
    fi
fi

# Check the original server (port 8001)
echo -e "${YELLOW}  ► Checking original R server (port 8001)...${NC}"
ORIGINAL_SERVER_RUNNING=false

# Method 1: Check PID file for original server
if [ -f .r_server_original.pid ]; then
    R_SERVER_PID=$(cat .r_server_original.pid)
    if ps -p $R_SERVER_PID > /dev/null; then
        echo -e "${GREEN}✓ Original R server is running (PID: $R_SERVER_PID)${NC}"
        ORIGINAL_SERVER_RUNNING=true
        
        # Try to ping the server API
        if command -v curl &> /dev/null; then
            R_SERVER_PING=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ping 2>/dev/null || echo "failed")
            if [ "$R_SERVER_PING" == "200" ]; then
                echo -e "  - API is responsive (ping: 200 OK)"
            else
                echo -e "  - ${RED}API is not responsive (ping: $R_SERVER_PING)${NC}"
            fi
        fi
    else
        echo -e "${RED}✗ Original R server is not running (PID file exists but process not found)${NC}"
        rm -f .r_server_original.pid
    fi
fi

# Method 2: Check port 8001
if [ "$ORIGINAL_SERVER_RUNNING" = false ]; then
    PORT_8001_PID=$(lsof -ti :8001 2>/dev/null)
    if [ ! -z "$PORT_8001_PID" ]; then
        echo -e "${GREEN}✓ Original R server is running on port 8001 (PID: $PORT_8001_PID)${NC}"
        echo -e "  - (PID file missing, consider restarting with ./start_system.sh)"
        ORIGINAL_SERVER_RUNNING=true
    else
        echo -e "${YELLOW}  -> Original R server is not running${NC}"
    fi
fi

# Check for backward compatibility with old PID file
if [ -f .r_server.pid ]; then
    R_SERVER_PID=$(cat .r_server.pid)
    if ps -p $R_SERVER_PID > /dev/null; then
        echo -e "${YELLOW}✓ Found old-style R server running (PID: $R_SERVER_PID)${NC}"
        echo -e "  - (Using old PID file format, consider restarting with ./start_system.sh)"
    else
        echo -e "${YELLOW}  -> Old PID file exists but process not found${NC}"
        rm -f .r_server.pid
    fi
fi

# Summary message
if [ "$DIRECT_SERVER_RUNNING" = true ] || [ "$ORIGINAL_SERVER_RUNNING" = true ]; then
    echo -e "${GREEN}✓ At least one R server is running${NC}"
else
    echo -e "${RED}✗ No R servers are running${NC}"
    echo -e "  - (You can start them with ./start_system.sh)"
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

# Check network connectivity
echo -e "${YELLOW}► Checking network connectivity...${NC}"
if command -v nc &> /dev/null; then
    # Check Redis
    if nc -z localhost 6379; then
        echo -e "${GREEN}✓ Redis port is reachable${NC}"
    else
        echo -e "${RED}✗ Redis port is not reachable${NC}"
    fi
    
    # Check Flask
    if nc -z localhost 8060; then
        echo -e "${GREEN}✓ Flask port is reachable${NC}"
    else
        echo -e "${RED}✗ Flask port is not reachable${NC}"
    fi
    
    # Check Flower
    if nc -z localhost 5555; then
        echo -e "${GREEN}✓ Flower port is reachable${NC}"
    else
        echo -e "${RED}✗ Flower port is not reachable${NC}"
    fi
    
    # Check Direct KNN R server
    if nc -z localhost 8000; then
        echo -e "${GREEN}✓ Direct KNN R server port 8000 is reachable${NC}"
    else
        # Check alternative port
        if nc -z localhost 8002; then
            echo -e "${GREEN}✓ Direct KNN R server alternative port 8002 is reachable${NC}"
        else
            echo -e "${RED}✗ Direct KNN R server ports are not reachable${NC}"
        fi
    fi
    
    # Check Original R server
    if nc -z localhost 8001; then
        echo -e "${GREEN}✓ Original R server port 8001 is reachable${NC}"
    else
        echo -e "${RED}✗ Original R server port is not reachable${NC}"
    fi
else
    echo -e "${YELLOW}► Network check skipped (nc command not available)${NC}"
fi

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}System Health Check Complete${NC}"
echo -e "${BLUE}====================================${NC}"