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

# Function to check if a process is running
is_process_running() {
    ps -p $1 > /dev/null 2>&1
    return $?
}

# Function to check if a process exists using pattern
find_process_by_pattern() {
    ps aux | grep "$1" | grep -v grep | awk '{print $2}'
}

# Stop Flask app - try multiple methods
echo -e "${YELLOW}► Stopping Flask app...${NC}"
FLASK_STOPPED=false

# Method 1: Use PID file
if [ -f .flask.pid ]; then
    FLASK_PID=$(cat .flask.pid)
    if is_process_running $FLASK_PID; then
        echo -e "${YELLOW}  -> Found Flask app with PID: $FLASK_PID from PID file${NC}"
        kill $FLASK_PID 2>/dev/null
        sleep 1
        if ! is_process_running $FLASK_PID; then
            echo -e "${GREEN}  -> Successfully stopped Flask app via PID file${NC}"
            FLASK_STOPPED=true
        else
            echo -e "${YELLOW}  -> Flask didn't stop gracefully, using SIGKILL${NC}"
            kill -9 $FLASK_PID 2>/dev/null
            FLASK_STOPPED=true
        fi
    else
        echo -e "${YELLOW}  -> Flask PID file exists but process is not running${NC}"
    fi
    rm -f .flask.pid
fi

# Method 2: Find by process name if not already stopped
if [ "$FLASK_STOPPED" = false ]; then
    FLASK_PID=$(find_process_by_pattern "python main.py")
    if [ ! -z "$FLASK_PID" ]; then
        echo -e "${YELLOW}  -> Found Flask app with PID: $FLASK_PID by process name${NC}"
        kill $FLASK_PID 2>/dev/null
        sleep 1
        if ! is_process_running $FLASK_PID; then
            echo -e "${GREEN}  -> Successfully stopped Flask app via process name${NC}"
            FLASK_STOPPED=true
        else
            echo -e "${YELLOW}  -> Flask didn't stop gracefully, using SIGKILL${NC}"
            kill -9 $FLASK_PID 2>/dev/null
            FLASK_STOPPED=true
        fi
    fi
fi

# Method 3: Check for process using the Flask port
PORT_PID=$(lsof -ti :8060 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
    echo -e "${YELLOW}  -> Found process using port 8060 with PID: $PORT_PID${NC}"
    kill $PORT_PID 2>/dev/null
    sleep 1
    if ! lsof -ti :8060 > /dev/null 2>&1; then
        echo -e "${GREEN}  -> Successfully stopped process using port 8060${NC}"
        FLASK_STOPPED=true
    else
        echo -e "${YELLOW}  -> Process didn't stop gracefully, using SIGKILL${NC}"
        kill -9 $PORT_PID 2>/dev/null
        FLASK_STOPPED=true
    fi
fi

if [ "$FLASK_STOPPED" = true ]; then
    echo -e "${GREEN}✓ Flask app stopped${NC}"
else
    echo -e "${YELLOW}► No Flask app process found${NC}"
fi

# Stop Celery workers
echo -e "${YELLOW}► Stopping Celery workers...${NC}"

# Method 1: Normal process pattern
CELERY_WORKERS=$(find_process_by_pattern "celery -A celery_app.celery worker")
if [ ! -z "$CELERY_WORKERS" ]; then
    echo -e "${YELLOW}  -> Found Celery workers: $CELERY_WORKERS${NC}"
    for pid in $CELERY_WORKERS; do
        kill $pid 2>/dev/null
    done
    sleep 1
    
    # Check if they're still running
    CELERY_WORKERS_AFTER=$(find_process_by_pattern "celery -A celery_app.celery worker")
    if [ ! -z "$CELERY_WORKERS_AFTER" ]; then
        echo -e "${YELLOW}  -> Workers didn't stop gracefully, using SIGKILL${NC}"
        for pid in $CELERY_WORKERS_AFTER; do
            kill -9 $pid 2>/dev/null
        done
    fi
    echo -e "${GREEN}  -> Celery workers stopped via process pattern${NC}"
else
    echo -e "${YELLOW}  -> No Celery workers found via process pattern${NC}"
fi

# Method 2: Check for any Python processes with celery in the command
CELERY_PYTHON=$(ps aux | grep "[p]ython.*celery" | awk '{print $2}')
if [ ! -z "$CELERY_PYTHON" ]; then
    echo -e "${YELLOW}  -> Found Python Celery processes: $CELERY_PYTHON${NC}"
    for pid in $CELERY_PYTHON; do
        kill -9 $pid 2>/dev/null
    done
    echo -e "${GREEN}  -> Python Celery processes stopped${NC}"
fi

echo -e "${GREEN}✓ Celery workers stopped${NC}"

# Stop Flower
echo -e "${YELLOW}► Stopping Flower...${NC}"
FLOWER_STOPPED=false

# Method 1: Normal process pattern
FLOWER_PROCESSES=$(find_process_by_pattern "celery -A celery_app.celery flower")
if [ ! -z "$FLOWER_PROCESSES" ]; then
    echo -e "${YELLOW}  -> Found Flower processes: $FLOWER_PROCESSES${NC}"
    for pid in $FLOWER_PROCESSES; do
        kill $pid 2>/dev/null
    done
    sleep 1
    
    # Check if they're still running
    FLOWER_AFTER=$(find_process_by_pattern "celery -A celery_app.celery flower")
    if [ ! -z "$FLOWER_AFTER" ]; then
        echo -e "${YELLOW}  -> Flower didn't stop gracefully, using SIGKILL${NC}"
        for pid in $FLOWER_AFTER; do
            kill -9 $pid 2>/dev/null
        done
    fi
    FLOWER_STOPPED=true
    echo -e "${GREEN}  -> Flower stopped via process pattern${NC}"
else
    echo -e "${YELLOW}  -> No Flower processes found via process pattern${NC}"
fi

# Method 2: Check for any processes with flower in the name
FLOWER_ANY=$(ps aux | grep "[f]lower" | grep -v grep | awk '{print $2}')
if [ ! -z "$FLOWER_ANY" ]; then
    echo -e "${YELLOW}  -> Found additional Flower processes: $FLOWER_ANY${NC}"
    for pid in $FLOWER_ANY; do
        kill -9 $pid 2>/dev/null
    done
    FLOWER_STOPPED=true
    echo -e "${GREEN}  -> Additional Flower processes stopped${NC}"
fi

# Method 3: Check for any processes on port 5555 (Flower's default port)
PORT_5555_PID=$(lsof -ti :5555 2>/dev/null)
if [ ! -z "$PORT_5555_PID" ]; then
    echo -e "${YELLOW}  -> Found process using port 5555 with PID: $PORT_5555_PID${NC}"
    kill -9 $PORT_5555_PID 2>/dev/null
    FLOWER_STOPPED=true
    echo -e "${GREEN}  -> Process using port 5555 forcibly stopped${NC}"
fi

if [ "$FLOWER_STOPPED" = true ]; then
    echo -e "${GREEN}✓ Flower stopped${NC}"
else
    echo -e "${YELLOW}  -> No Flower processes found to stop${NC}"
fi

# Kill any remaining Python processes related to Celery
CELERY_PYTHON=$(ps aux | grep "[p]ython.*celery" | awk '{print $2}')
if [ ! -z "$CELERY_PYTHON" ]; then
    echo -e "${YELLOW}► Found additional Python Celery processes: $CELERY_PYTHON${NC}"
    for pid in $CELERY_PYTHON; do
        kill -9 $pid 2>/dev/null
    done
    echo -e "${GREEN}✓ Additional Python Celery processes stopped${NC}"
fi

# Stop R servers
echo -e "${YELLOW}► Stopping R prediction servers...${NC}"

# Check if we should preserve RStudio server
PRESERVE_RSTUDIO=false
if [ "$1" == "--preserve-rstudio" ]; then
    PRESERVE_RSTUDIO=true
fi

# Check for RStudio process on port 8000
RSTUDIO_RUNNING=false

# First check the --preserve-rstudio flag
if [ "$PRESERVE_RSTUDIO" = true ]; then
    echo -e "${YELLOW}  -> Preserving R server as requested by --preserve-rstudio flag${NC}"
    RSTUDIO_RUNNING=true
fi

# Then check if port 8000 is used by RStudio
PORT_8000_PID=$(lsof -ti :8000 2>/dev/null)
if [ ! -z "$PORT_8000_PID" ] && [ "$RSTUDIO_RUNNING" = false ]; then
    # Check if this is an R process related to RStudio
    # grep -i for case insensitive matching of RStudio
    if ps -p $PORT_8000_PID -o command | grep -qi "RStudio"; then
        echo -e "${YELLOW}  -> R server is running in RStudio (PID: $PORT_8000_PID)${NC}"
        echo -e "${YELLOW}  -> Not stopping RStudio-managed server${NC}"
        echo -e "${YELLOW}  -> Please stop the server manually in RStudio${NC}"
        RSTUDIO_RUNNING=true
    fi
fi

# Stop the direct KNN server on port 8000 (if not RStudio)
if [ "$RSTUDIO_RUNNING" = false ]; then
    echo -e "${YELLOW}► Stopping direct KNN R server on port 8000...${NC}"
    DIRECT_SERVER_STOPPED=false
    
    # Check for PID file
    if [ -f .r_server_direct.pid ]; then
        R_SERVER_PID=$(cat .r_server_direct.pid)
        if ps -p $R_SERVER_PID > /dev/null; then
            echo -e "${YELLOW}  -> Found direct KNN R server with PID: $R_SERVER_PID${NC}"
            kill $R_SERVER_PID 2>/dev/null
            sleep 1
            if ! ps -p $R_SERVER_PID > /dev/null; then
                echo -e "${GREEN}  -> Direct KNN R server stopped gracefully${NC}"
            else
                echo -e "${YELLOW}  -> Direct KNN R server didn't stop gracefully, using SIGKILL${NC}"
                kill -9 $R_SERVER_PID 2>/dev/null
                echo -e "${GREEN}  -> Direct KNN R server forcibly stopped${NC}"
            fi
            DIRECT_SERVER_STOPPED=true
        fi
        rm -f .r_server_direct.pid
    fi
    
    # Check for port 8000 or port 8002 (alternative port)
    for PORT in 8000 8002; do
        PORT_PID=$(lsof -ti :$PORT 2>/dev/null)
        if [ ! -z "$PORT_PID" ]; then
            # Skip if it's RStudio
            if ps -p $PORT_PID -o command | grep -qi "RStudio"; then
                echo -e "${YELLOW}  -> RStudio detected on port $PORT, preserving${NC}"
                continue
            fi
            
            echo -e "${YELLOW}  -> Found R process using port $PORT with PID: $PORT_PID${NC}"
            kill $PORT_PID 2>/dev/null
            sleep 1
            if ! lsof -ti :$PORT > /dev/null 2>&1; then
                echo -e "${GREEN}  -> R process on port $PORT stopped gracefully${NC}"
            else
                echo -e "${YELLOW}  -> R process on port $PORT didn't stop gracefully, using SIGKILL${NC}"
                kill -9 $PORT_PID 2>/dev/null
                echo -e "${GREEN}  -> R process on port $PORT forcibly stopped${NC}"
            fi
            DIRECT_SERVER_STOPPED=true
        fi
    done
    
    if [ "$DIRECT_SERVER_STOPPED" = false ]; then
        echo -e "${YELLOW}  -> No direct KNN R server found to stop${NC}"
    fi
fi

# Stop the original server on port 8001
echo -e "${YELLOW}► Stopping original R server on port 8001...${NC}"
ORIGINAL_SERVER_STOPPED=false

# Check for PID file
if [ -f .r_server_original.pid ]; then
    R_SERVER_PID=$(cat .r_server_original.pid)
    if ps -p $R_SERVER_PID > /dev/null; then
        echo -e "${YELLOW}  -> Found original R server with PID: $R_SERVER_PID${NC}"
        kill $R_SERVER_PID 2>/dev/null
        sleep 1
        if ! ps -p $R_SERVER_PID > /dev/null; then
            echo -e "${GREEN}  -> Original R server stopped gracefully${NC}"
        else
            echo -e "${YELLOW}  -> Original R server didn't stop gracefully, using SIGKILL${NC}"
            kill -9 $R_SERVER_PID 2>/dev/null
            echo -e "${GREEN}  -> Original R server forcibly stopped${NC}"
        fi
        ORIGINAL_SERVER_STOPPED=true
    fi
    rm -f .r_server_original.pid
fi

# Check for port 8001
PORT_8001_PID=$(lsof -ti :8001 2>/dev/null)
if [ ! -z "$PORT_8001_PID" ]; then
    echo -e "${YELLOW}  -> Found process using port 8001 with PID: $PORT_8001_PID${NC}"
    kill $PORT_8001_PID 2>/dev/null
    sleep 1
    if ! lsof -ti :8001 > /dev/null 2>&1; then
        echo -e "${GREEN}  -> Process on port 8001 stopped gracefully${NC}"
    else
        echo -e "${YELLOW}  -> Process on port 8001 didn't stop gracefully, using SIGKILL${NC}"
        kill -9 $PORT_8001_PID 2>/dev/null
        echo -e "${GREEN}  -> Process on port 8001 forcibly stopped${NC}"
    fi
    ORIGINAL_SERVER_STOPPED=true
fi

if [ "$ORIGINAL_SERVER_STOPPED" = false ]; then
    echo -e "${YELLOW}  -> No original R server found to stop${NC}"
fi

# For backward compatibility, also check the old PID file
if [ -f .r_server.pid ]; then
    R_SERVER_PID=$(cat .r_server.pid)
    if ps -p $R_SERVER_PID > /dev/null; then
        echo -e "${YELLOW}  -> Found old R server with PID: $R_SERVER_PID${NC}"
        kill -9 $R_SERVER_PID 2>/dev/null
        echo -e "${GREEN}  -> Old R server forcibly stopped${NC}"
    fi
    rm -f .r_server.pid
fi

# Stop Redis (optional)
STOP_REDIS=false
if [ "$1" == "--stop-redis" ] || [ "$2" == "--stop-redis" ]; then
    STOP_REDIS=true
fi

if [ "$STOP_REDIS" = true ]; then
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
echo -e "${GREEN}✓ All systems stopped!${NC}"
echo -e "${BLUE}====================================${NC}"

# Final status check
echo -e "${BLUE}====================================${NC}"
echo -e "${YELLOW}System Status:${NC}"
echo -e "${BLUE}====================================${NC}"

echo -ne "Flask (port 8060): "
if lsof -ti :8060 > /dev/null 2>&1; then
    echo -e "${RED}Still Running${NC}"
else
    echo -e "${GREEN}Stopped${NC}"
fi

echo -ne "Celery worker: "
if ps aux | grep "[c]elery -A celery_app.celery worker" > /dev/null; then
    echo -e "${RED}Still Running${NC}"
else
    echo -e "${GREEN}Stopped${NC}"
fi

echo -ne "Flower (port 5555): "
if lsof -ti :5555 > /dev/null 2>&1; then
    echo -e "${RED}Still Running${NC}"
else
    echo -e "${GREEN}Stopped${NC}"
fi

echo -ne "Redis: "
if redis-cli ping &> /dev/null; then
    if [ "$1" == "--stop-redis" ]; then
        echo -e "${RED}Still Running${NC}"
    else
        echo -e "${GREEN}Running (intentionally)${NC}"
    fi
else
    echo -e "${RED}Not Running${NC}"
fi

echo -ne "Direct KNN R server (port 8000): "
if lsof -ti :8000 > /dev/null 2>&1; then
    # Check if it's RStudio
    if lsof -ti :8000 | xargs ps -p | grep -q "RStudio"; then
        echo -e "${GREEN}RStudio session (preserved)${NC}"
    else
        echo -e "${RED}Still Running${NC}"
    fi
else
    echo -e "${GREEN}Stopped${NC}"
fi

echo -ne "Original R server (port 8001): "
if lsof -ti :8001 > /dev/null 2>&1; then
    echo -e "${RED}Still Running${NC}"
else
    echo -e "${GREEN}Stopped${NC}"
fi