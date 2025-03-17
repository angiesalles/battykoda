#!/bin/bash
# Start the R prediction server

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
echo -e "${BLUE}Starting R Prediction Server${NC}"
echo -e "${BLUE}====================================${NC}"

# Check if R is installed
if ! command -v Rscript &> /dev/null; then
    echo -e "${RED}Error: Rscript not found. Please install R.${NC}"
    echo -e "${YELLOW}On macOS: brew install r${NC}"
    echo -e "${YELLOW}On Linux: sudo apt install r-base${NC}"
    exit 1
fi

# Check if the plumber package is installed
echo -e "${YELLOW}► Checking R packages...${NC}"
Rscript -e "if(!requireNamespace('plumber', quietly = TRUE)) { cat('Installing plumber package...'); install.packages('plumber', repos = 'https://cloud.r-project.org'); }"

# Start the R server
echo -e "${YELLOW}► Starting R prediction server...${NC}"
echo -e "${YELLOW}► Log file: logs/r_server.log${NC}"

# Run in background
nohup Rscript r_prediction_server.R > logs/r_server.log 2>&1 &
R_SERVER_PID=$!
echo $R_SERVER_PID > .r_server.pid

# Wait a moment for server to start
sleep 3

# Check if server is running
if ps -p $R_SERVER_PID > /dev/null; then
    echo -e "${GREEN}✓ R prediction server started on port 8000 (PID: $R_SERVER_PID)${NC}"
    echo -e "${YELLOW}► API Endpoints:${NC}"
    echo -e "  - ${GREEN}http://localhost:8000/ping${NC} - Check server status"
    echo -e "  - ${GREEN}http://localhost:8000/classify${NC} - Classify bat calls"
    echo -e "  - ${GREEN}http://localhost:8000/call_types${NC} - Get available call types"
    echo -e "${YELLOW}► API Documentation: ${GREEN}http://localhost:8000/__docs__/${NC}"
else
    echo -e "${RED}✗ Failed to start R prediction server. Check logs/r_server.log for details.${NC}"
    exit 1
fi

echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}✓ R prediction server started!${NC}"
echo -e "${BLUE}====================================${NC}"