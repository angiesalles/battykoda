#!/bin/bash
# Production shutdown script for BattyCoda using Docker Compose

# Set up colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Stopping BattyCoda System${NC}"
echo -e "${BLUE}====================================${NC}"

# Use the appropriate Docker Compose command based on what's available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

echo -e "${YELLOW}► Stopping all services...${NC}"
# Check if we need sudo for Docker
if docker info &>/dev/null; then
    $DOCKER_COMPOSE down
else
    echo -e "${YELLOW}► Need elevated privileges for Docker. Using sudo...${NC}"
    sudo $DOCKER_COMPOSE down
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All services stopped successfully!${NC}"
else
    echo -e "${RED}There was an error stopping the services.${NC}"
    
    # Try force stopping
    echo -e "${YELLOW}► Attempting force stop...${NC}"
    $DOCKER_COMPOSE down --timeout 1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Force stop successful!${NC}"
    else
        echo -e "${RED}Force stop failed. You may need to manually stop containers.${NC}"
        echo -e "${YELLOW}Try: docker ps${NC}"
        echo -e "${YELLOW}Then: docker stop <container_id>${NC}"
    fi
fi

echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}System is now stopped!${NC}"
echo -e "${BLUE}====================================${NC}"

# Add option to remove volumes
if [ "$1" == "--clean" ] || [ "$1" == "-c" ]; then
    echo -e "${YELLOW}► Removing all volumes and data...${NC}"
    $DOCKER_COMPOSE down -v
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ All volumes removed!${NC}"
    else
        echo -e "${RED}There was an error removing volumes.${NC}"
    fi
    
    echo -e "${YELLOW}Note: This has removed all persistent data. The next startup will create fresh containers.${NC}"
fi