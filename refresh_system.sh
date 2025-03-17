#!/bin/bash
# Script to refresh the BattyCoda system after code changes
# This stops all components (except Redis), purges the task queue,
# and then restarts the system

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

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Refreshing BattyCoda System${NC}"
echo -e "${BLUE}====================================${NC}"

# First, stop all components
echo -e "${YELLOW}► Stopping all components...${NC}"
./stop_system.sh
echo -e "${GREEN}✓ All components stopped${NC}"

# Purge Celery tasks
echo -e "${YELLOW}► Purging Celery task queue...${NC}"
if command -v celery &> /dev/null; then
    celery -A celery_app.celery purge -f || echo -e "${RED}Failed to purge task queue${NC}"
    echo -e "${GREEN}✓ Task queue purged${NC}"
else
    echo -e "${RED}⚠ Celery not found. Skipping task purge.${NC}"
fi

# Check for Python file syntax errors
echo -e "${YELLOW}► Checking for Python syntax errors...${NC}"
SYNTAX_ERROR=0
for file in $(find . -name "*.py" -not -path "./venv/*" -not -path "./.env/*"); do
    python -m py_compile $file 2>/dev/null || {
        echo -e "${RED}⚠ Syntax error in $file${NC}"
        python -m py_compile $file
        SYNTAX_ERROR=1
    }
done

if [ $SYNTAX_ERROR -eq 1 ]; then
    echo -e "${RED}⚠ Syntax errors found in Python files. Please fix before continuing.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ No syntax errors found${NC}"

# Clean Redis cache (optional)
if [ "$1" == "--clean-cache" ]; then
    echo -e "${YELLOW}► Cleaning Redis cache...${NC}"
    if command -v redis-cli &> /dev/null && redis-cli ping &> /dev/null; then
        redis-cli flushall || echo -e "${RED}Failed to flush Redis cache${NC}"
        echo -e "${GREEN}✓ Redis cache cleaned${NC}"
    else
        echo -e "${RED}⚠ Redis not running. Cannot clean cache.${NC}"
    fi
fi

# Restart the system
echo -e "${YELLOW}► Restarting BattyCoda...${NC}"
./start_system.sh

echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}✓ System refresh complete!${NC}"
echo -e "${BLUE}====================================${NC}"