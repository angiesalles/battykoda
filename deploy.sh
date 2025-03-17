#!/bin/bash
# Deployment script for BattyCoda

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
echo -e "${BLUE}Deploying BattyCoda${NC}"
echo -e "${BLUE}====================================${NC}"

# Create deployment log
mkdir -p logs
LOG_FILE="logs/deployment_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Deployment started at $(date)"

# Pull latest changes from git
echo -e "${YELLOW}► Pulling latest code from git...${NC}"
git pull

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to pull changes from git. Aborting deployment.${NC}"
    exit 1
fi

# Update dependencies
echo -e "${YELLOW}► Updating dependencies...${NC}"
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to update dependencies. Continuing anyway, but be prepared for potential issues.${NC}"
fi

# Run database migrations
echo -e "${YELLOW}► Running database migrations...${NC}"
python add_cloudflare_fields.py

# Stop the current services
echo -e "${YELLOW}► Stopping services...${NC}"
./battycoda docker-stop

# Start the services with new code
echo -e "${YELLOW}► Starting services with updated code...${NC}"
./battycoda docker-start

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Deployment completed successfully at $(date)${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "${YELLOW}To view logs:${NC} ./battycoda docker-logs"
    echo -e "${BLUE}====================================${NC}"
else
    echo -e "${RED}⚠ Deployment encountered issues. Check the logs.${NC}"
    exit 1
fi