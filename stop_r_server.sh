#!/bin/bash
# Stop the R prediction server

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
echo -e "${BLUE}Stopping R Prediction Server${NC}"
echo -e "${BLUE}====================================${NC}"

R_SERVER_STOPPED=false

# Method 1: Use PID file
if [ -f .r_server.pid ]; then
    R_SERVER_PID=$(cat .r_server.pid)
    if ps -p $R_SERVER_PID > /dev/null; then
        echo -e "${YELLOW}► Found R server with PID: $R_SERVER_PID${NC}"
        kill $R_SERVER_PID
        sleep 1
        if ! ps -p $R_SERVER_PID > /dev/null; then
            echo -e "${GREEN}✓ R server stopped${NC}"
            R_SERVER_STOPPED=true
        else
            echo -e "${YELLOW}► R server didn't stop gracefully, using SIGKILL${NC}"
            kill -9 $R_SERVER_PID
            echo -e "${GREEN}✓ R server forcibly stopped${NC}"
            R_SERVER_STOPPED=true
        fi
    else
        echo -e "${YELLOW}► R server not running (PID: $R_SERVER_PID not found)${NC}"
    fi
    rm -f .r_server.pid
fi

# Method 2: Check for any R processes matching our server
if [ "$R_SERVER_STOPPED" = false ]; then
    R_PROCS=$(ps aux | grep "[R]script.*r_prediction_server\.R" | awk '{print $2}')
    if [ ! -z "$R_PROCS" ]; then
        echo -e "${YELLOW}► Found R server processes: $R_PROCS${NC}"
        for pid in $R_PROCS; do
            echo -e "${YELLOW}► Killing process $pid${NC}"
            kill -9 $pid
        done
        echo -e "${GREEN}✓ R server processes stopped${NC}"
        R_SERVER_STOPPED=true
    fi
fi

# Method 3: Check for anything on port 8000
PORT_8000_PID=$(lsof -ti :8000 2>/dev/null)
if [ ! -z "$PORT_8000_PID" ]; then
    echo -e "${YELLOW}► Found process using port 8000 with PID: $PORT_8000_PID${NC}"
    kill -9 $PORT_8000_PID 2>/dev/null
    echo -e "${GREEN}✓ Process on port 8000 stopped${NC}"
    R_SERVER_STOPPED=true
fi

if [ "$R_SERVER_STOPPED" = false ]; then
    echo -e "${YELLOW}► No R server processes found to stop${NC}"
fi

echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}✓ R server shutdown complete!${NC}"
echo -e "${BLUE}====================================${NC}"