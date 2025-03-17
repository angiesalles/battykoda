#!/bin/bash
#
# Script to start both R prediction servers (original and direct KNN version)
#

# Set up colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Change to the script directory
cd "$(dirname "$0")"

# Create logs directory if it doesn't exist
mkdir -p logs

echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}Starting BattyCoda R Servers${NC}"
echo -e "${BLUE}==================================${NC}"

# Kill any existing R servers
echo -e "${YELLOW}► Checking for existing R servers...${NC}"
pkill -f "Rscript.*r_prediction_server.R" || true
pkill -f "Rscript.*r_server_direct.R" || true

# Check if ports are in use by other processes
PORT_8000_PID=$(lsof -ti :8000 2>/dev/null)
PORT_8001_PID=$(lsof -ti :8001 2>/dev/null)

# Check if port 8000 is used by RStudio
RSTUDIO_DETECTED=false
if [ ! -z "$PORT_8000_PID" ]; then
    if ps -p $PORT_8000_PID -o command | grep -qi "RStudio"; then
        echo -e "${YELLOW}► RStudio detected on port 8000 (PID: $PORT_8000_PID)${NC}"
        echo -e "${YELLOW}  -> Will use port 8002 for direct KNN server${NC}"
        DIRECT_PORT=8002
        RSTUDIO_DETECTED=true
    else
        echo -e "${YELLOW}► Killing process on port 8000 (PID: $PORT_8000_PID)${NC}"
        kill $PORT_8000_PID 2>/dev/null || kill -9 $PORT_8000_PID 2>/dev/null
        DIRECT_PORT=8000
    fi
else
    DIRECT_PORT=8000
fi

# Kill any process on port 8001
if [ ! -z "$PORT_8001_PID" ]; then
    echo -e "${YELLOW}► Killing process on port 8001 (PID: $PORT_8001_PID)${NC}"
    kill $PORT_8001_PID 2>/dev/null || kill -9 $PORT_8001_PID 2>/dev/null
fi

# Start the servers in background
echo -e "${YELLOW}► Starting R prediction servers...${NC}"

# Original server on port 8001
echo -e "${YELLOW}  -> Starting original R server on port 8001...${NC}"
> logs/r_server_original.log  # Clear log file
ORIGINAL_CMD="Rscript r_prediction_server.R --port=8001"
echo "$ORIGINAL_CMD" > logs/r_server_original.log  # Log the command
nohup $ORIGINAL_CMD >> logs/r_server_original.log 2>&1 &
ORIGINAL_PID=$!
echo $ORIGINAL_PID > .r_server_original.pid  # Save PID to file

# Direct KNN server
echo -e "${YELLOW}  -> Starting direct KNN R server on port ${DIRECT_PORT}...${NC}"
> logs/r_server_direct.log  # Clear log file
if [ "$DIRECT_PORT" = "8000" ]; then
    DIRECT_CMD="Rscript r_server_direct.R"
else
    DIRECT_CMD="Rscript r_server_direct.R --port=${DIRECT_PORT}"
fi
echo "$DIRECT_CMD" > logs/r_server_direct.log  # Log the command
nohup $DIRECT_CMD >> logs/r_server_direct.log 2>&1 &
DIRECT_PID=$!
echo $DIRECT_PID > .r_server_direct.pid  # Save PID to file

# Wait for servers to start
echo -e "${YELLOW}► Waiting for servers to start (10 seconds max)...${NC}"

# Function to check if a port is responding
check_port() {
    local port=$1
    local max_attempts=10
    local attempt=0
    local success=false
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:$port/ping | grep -q "alive"; then
            success=true
            break
        fi
        echo -e "${YELLOW}  -> Waiting for port $port (attempt $((attempt+1)))${NC}"
        sleep 1
        attempt=$((attempt+1))
    done
    
    echo $success
}

# Check direct server
if [ "$RSTUDIO_DETECTED" = true ]; then
    echo -e "${YELLOW}► Testing direct KNN server on port ${DIRECT_PORT}...${NC}"
    DIRECT_RUNNING=$(check_port $DIRECT_PORT)
else
    echo -e "${YELLOW}► Testing direct KNN server on port 8000...${NC}"
    DIRECT_RUNNING=$(check_port 8000)
fi

# Check original server
echo -e "${YELLOW}► Testing original server on port 8001...${NC}"
ORIGINAL_RUNNING=$(check_port 8001)

# Final status check
echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}R Server Status${NC}"
echo -e "${BLUE}==================================${NC}"

if [ "$DIRECT_RUNNING" = "true" ]; then
    echo -e "${GREEN}✓ Direct KNN server is running on port $DIRECT_PORT (PID: $DIRECT_PID)${NC}"
    echo -e "  -> Test with: curl http://localhost:$DIRECT_PORT/ping"
else
    if ps -p $DIRECT_PID > /dev/null; then
        echo -e "${YELLOW}⚠ Direct KNN server process is running (PID: $DIRECT_PID) but not responding${NC}"
        echo -e "  -> Check logs/r_server_direct.log for errors"
    else
        echo -e "${RED}✗ Direct KNN server failed to start${NC}"
        echo -e "  -> Check logs/r_server_direct.log for errors"
    fi
fi

if [ "$ORIGINAL_RUNNING" = "true" ]; then
    echo -e "${GREEN}✓ Original server is running on port 8001 (PID: $ORIGINAL_PID)${NC}"
    echo -e "  -> Test with: curl http://localhost:8001/ping"
else
    if ps -p $ORIGINAL_PID > /dev/null; then
        echo -e "${YELLOW}⚠ Original server process is running (PID: $ORIGINAL_PID) but not responding${NC}"
        echo -e "  -> Check logs/r_server_original.log for errors"
    else
        echo -e "${RED}✗ Original server failed to start${NC}"
        echo -e "  -> Check logs/r_server_original.log for errors"
    fi
fi

# Overall status
if [ "$DIRECT_RUNNING" = "true" ] || [ "$ORIGINAL_RUNNING" = "true" ]; then
    echo -e "${GREEN}✓ At least one R server is running and responding${NC}"
else
    echo -e "${RED}✗ No R servers are running and responding${NC}"
    echo -e "  -> Check logs for errors"
fi

echo -e "${BLUE}==================================${NC}"
echo -e "${YELLOW}Log files:${NC}"
echo -e "  Direct KNN server: ${BLUE}logs/r_server_direct.log${NC}"
echo -e "  Original server:   ${BLUE}logs/r_server_original.log${NC}"
echo -e "${BLUE}==================================${NC}"