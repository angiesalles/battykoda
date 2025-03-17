#!/bin/bash
# Master script to start the entire BattyCoda system
# This starts Redis, Celery worker, Flower, and the Flask app

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
echo -e "${BLUE}Starting BattyCoda System${NC}"
echo -e "${BLUE}====================================${NC}"

# First, let's make sure any existing processes are stopped
echo -e "${YELLOW}► Ensuring previous processes are stopped...${NC}"
./stop_system.sh > /dev/null 2>&1 || true

# Check if port 8060 is in use
PORT_IN_USE=$(lsof -i :8060 | grep LISTEN)
if [ ! -z "$PORT_IN_USE" ]; then
    echo -e "${RED}⚠ Port 8060 is still in use. Forcibly terminating process...${NC}"
    lsof -i :8060 -t | xargs kill -9 2>/dev/null || true
fi

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
            # Wait for Redis to start
            MAX_ATTEMPTS=5
            ATTEMPT=0
            while ! redis-cli ping &> /dev/null && [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
                echo -e "${YELLOW}► Waiting for Redis to start (attempt $((ATTEMPT+1))/${MAX_ATTEMPTS})...${NC}"
                sleep 1
                ATTEMPT=$((ATTEMPT+1))
            done
            if ! redis-cli ping &> /dev/null; then
                echo -e "${RED}⚠ Redis failed to start after ${MAX_ATTEMPTS} attempts.${NC}"
                exit 1
            fi
        else
            # Linux
            sudo systemctl start redis-server || { echo -e "${RED}Failed to start Redis${NC}"; exit 1; }
            # Wait for Redis to start
            MAX_ATTEMPTS=5
            ATTEMPT=0
            while ! redis-cli ping &> /dev/null && [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
                echo -e "${YELLOW}► Waiting for Redis to start (attempt $((ATTEMPT+1))/${MAX_ATTEMPTS})...${NC}"
                sleep 1
                ATTEMPT=$((ATTEMPT+1))
            done
            if ! redis-cli ping &> /dev/null; then
                echo -e "${RED}⚠ Redis failed to start after ${MAX_ATTEMPTS} attempts.${NC}"
                exit 1
            fi
        fi
        echo -e "${GREEN}✓ Redis started${NC}"
    fi
else
    echo -e "${RED}⚠ Redis CLI not found. Please install Redis first.${NC}"
    echo -e "${YELLOW}On macOS: brew install redis${NC}"
    echo -e "${YELLOW}On Linux: sudo apt install redis-server${NC}"
    exit 1
fi

# Start R servers in background (if available and not already running)
echo -e "${YELLOW}► Checking R prediction servers...${NC}"

# First check if the R server script exists
if [ -f "./r_server_direct.R" ] && [ -f "./r_prediction_server.R" ] && command -v Rscript &> /dev/null; then
    # Check if we have the required R packages
    if Rscript -e "cat(requireNamespace('plumber', quietly = TRUE) && requireNamespace('class', quietly = TRUE))" | grep -q "TRUE"; then
        # Check if servers are already running
        # Check for direct KNN server on port 8000
        PORT_8000_USED=$(lsof -ti :8000 2>/dev/null)
        if [ ! -z "$PORT_8000_USED" ]; then
            # Check if it's RStudio
            if ps -p $PORT_8000_USED -o command | grep -q "RStudio"; then
                echo -e "${GREEN}✓ RStudio session detected on port 8000 (PID: $PORT_8000_USED)${NC}"
                echo -e "${YELLOW}  -> Preserving RStudio session, not starting direct KNN server${NC}"
                echo -e "${YELLOW}  -> Will try alternative port 8002 for direct KNN server${NC}"
                DIRECT_SERVER_PORT=8002
            else
                echo -e "${GREEN}✓ Server already running on port 8000 (PID: $PORT_8000_USED)${NC}"
                # Still save the PID so we have a record of it
                echo $PORT_8000_USED > .r_server_direct.pid
                DIRECT_SERVER_RUNNING=true
            fi
        else
            DIRECT_SERVER_PORT=8000
        fi
        
        # Check for original server on port 8001
        PORT_8001_USED=$(lsof -ti :8001 2>/dev/null)
        if [ ! -z "$PORT_8001_USED" ]; then
            echo -e "${GREEN}✓ Original R server already running on port 8001 (PID: $PORT_8001_USED)${NC}"
            # Still save the PID so we have a record of it
            echo $PORT_8001_USED > .r_server_original.pid
            ORIGINAL_SERVER_RUNNING=true
        fi
        
        # Start the direct KNN server if not already running
        if [ -z "$DIRECT_SERVER_RUNNING" ]; then
            echo -e "${YELLOW}► Starting direct KNN R server on port ${DIRECT_SERVER_PORT}...${NC}"
            # Create log file
            > logs/r_server_direct.log
            
            # Start the server
            if [ "$DIRECT_SERVER_PORT" == "8000" ]; then
                nohup Rscript r_server_direct.R > logs/r_server_direct.log 2>&1 &
            else
                # Use alternative port
                nohup Rscript -e "source('r_server_direct.R'); start_server(port = ${DIRECT_SERVER_PORT})" > logs/r_server_direct.log 2>&1 &
            fi
            
            DIRECT_SERVER_PID=$!
            echo $DIRECT_SERVER_PID > .r_server_direct.pid
            
            # Wait a moment for server to start
            sleep 2
            
            # Check if it's running
            if ps -p $DIRECT_SERVER_PID > /dev/null; then
                echo -e "${GREEN}✓ Direct KNN R server started on port ${DIRECT_SERVER_PORT} (PID: $DIRECT_SERVER_PID)${NC}"
            else
                echo -e "${YELLOW}⚠ Direct KNN R server may not have started properly. Check logs/r_server_direct.log${NC}"
            fi
        fi
        
        # Start the original server if not already running
        if [ -z "$ORIGINAL_SERVER_RUNNING" ]; then
            echo -e "${YELLOW}► Starting original R server on port 8001...${NC}"
            # Create log file
            > logs/r_server_original.log
            
            # Start the server
            nohup Rscript r_prediction_server.R --port 8001 > logs/r_server_original.log 2>&1 &
            ORIGINAL_SERVER_PID=$!
            echo $ORIGINAL_SERVER_PID > .r_server_original.pid
            
            # Wait a moment for server to start
            sleep 2
            
            # Check if it's running
            if ps -p $ORIGINAL_SERVER_PID > /dev/null; then
                echo -e "${GREEN}✓ Original R server started on port 8001 (PID: $ORIGINAL_SERVER_PID)${NC}"
            else
                echo -e "${YELLOW}⚠ Original R server may not have started properly. Check logs/r_server_original.log${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}  -> Required R packages not found, skipping R servers${NC}"
    fi
else
    echo -e "${YELLOW}  -> R server scripts not found, skipping R servers${NC}"
fi

# Start Celery worker in background
echo -e "${YELLOW}► Starting Celery worker...${NC}"
# Clear the log file to start fresh
> logs/celery_worker.log

# Use nohup to ensure Celery runs completely in the background
nohup celery -A celery_app.celery worker --loglevel=info --logfile=logs/celery_worker.log > /dev/null 2>&1 &
CELERY_PID=$!

# Verify Celery started correctly by checking the log file
MAX_ATTEMPTS=10
ATTEMPT=0
CELERY_STARTED=false
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if grep -q "ready" logs/celery_worker.log; then
        CELERY_STARTED=true
        break
    fi
    echo -e "${YELLOW}► Waiting for Celery worker to start (attempt $((ATTEMPT+1))/${MAX_ATTEMPTS})...${NC}"
    sleep 1
    ATTEMPT=$((ATTEMPT+1))
done

if [ "$CELERY_STARTED" = true ]; then
    echo -e "${GREEN}✓ Celery worker started (PID: $CELERY_PID)${NC}"
else
    echo -e "${RED}⚠ Celery worker may not have started properly. Check logs/celery_worker.log${NC}"
    # Continue anyway, as it might still be starting
fi

# Start Flower in background
echo -e "${YELLOW}► Starting Flower monitoring...${NC}"
> logs/flower.log

# Use nohup to ensure Flower runs completely in the background
nohup celery -A celery_app.celery flower --port=5555 --logfile=logs/flower.log > /dev/null 2>&1 &
FLOWER_PID=$!
sleep 2

# Verify Flower is running by checking if the port is in use
if lsof -i :5555 | grep LISTEN > /dev/null; then
    echo -e "${GREEN}✓ Flower started at http://localhost:5555 (PID: $FLOWER_PID)${NC}"
else
    echo -e "${YELLOW}⚠ Flower may not have started correctly. Check logs/flower.log${NC}"
    # Continue anyway, as it might still be starting
fi

# Start Flask app
echo -e "${YELLOW}► Starting Flask application...${NC}"
> logs/flask_app.log
python main.py > logs/flask_app.log 2>&1 &
FLASK_PID=$!
echo $FLASK_PID > .flask.pid

# Verify Flask is running
MAX_ATTEMPTS=15
ATTEMPT=0
FLASK_STARTED=false
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if lsof -i :8060 | grep LISTEN > /dev/null; then
        FLASK_STARTED=true
        break
    fi
    echo -e "${YELLOW}► Waiting for Flask to start (attempt $((ATTEMPT+1))/${MAX_ATTEMPTS})...${NC}"
    sleep 1
    ATTEMPT=$((ATTEMPT+1))
done

if [ "$FLASK_STARTED" = true ]; then
    echo -e "${GREEN}✓ Flask app started at http://localhost:8060 (PID: $FLASK_PID)${NC}"
else
    echo -e "${RED}⚠ Flask app may not have started properly. Check logs/flask_app.log${NC}"
    # Continue anyway, to show all the status info
fi

echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}✓ All systems started!${NC}"
echo -e "${BLUE}====================================${NC}"
echo -e "Flask app: ${GREEN}http://localhost:8060${NC}"
echo -e "Flower dashboard: ${GREEN}http://localhost:5555${NC}"
echo -e "Log files are in: ${YELLOW}${SCRIPT_DIR}/logs${NC}"
echo -e "To stop the system, run: ${YELLOW}./stop_system.sh${NC}"

# Final status check
echo -e "${BLUE}====================================${NC}"
echo -e "${YELLOW}System Status:${NC}"
echo -e "${BLUE}====================================${NC}"
echo -ne "Redis: "
if redis-cli ping &> /dev/null; then
    echo -e "${GREEN}Running${NC}"
else
    echo -e "${RED}Not Running${NC}"
fi

echo -ne "Celery worker: "
if ps aux | grep "[c]elery -A celery_app.celery worker" > /dev/null; then
    echo -e "${GREEN}Running${NC}"
else 
    echo -e "${RED}Not Running${NC}"
fi

echo -ne "Flower: "
if lsof -i :5555 | grep LISTEN > /dev/null; then
    echo -e "${GREEN}Running${NC}"
else
    echo -e "${RED}Not Running${NC}"
fi

echo -ne "Flask: "
if lsof -i :8060 | grep LISTEN > /dev/null; then
    echo -e "${GREEN}Running${NC}"
else
    echo -e "${RED}Not Running${NC}"
fi

# Explicitly return success
exit 0