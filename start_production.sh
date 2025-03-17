#!/bin/bash
# Production startup script for BattyCoda using Docker Compose

# Set up colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Starting BattyCoda System with Docker${NC}"
echo -e "${BLUE}====================================${NC}"

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed. Please install Docker first.${NC}"
    echo -e "${YELLOW}Visit https://docs.docker.com/get-docker/ for installation instructions.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed. Please install Docker Compose first.${NC}"
    echo -e "${YELLOW}Visit https://docs.docker.com/compose/install/ for installation instructions.${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${YELLOW}► Creating necessary directories...${NC}"
mkdir -p data/home logs static/tempdata

# Build and start the Docker Compose services
echo -e "${YELLOW}► Starting Docker Compose services...${NC}"

# Use the appropriate Docker Compose command based on what's available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

# Check if we need sudo for Docker
if docker info &>/dev/null; then
    $DOCKER_COMPOSE up -d --build
else
    echo -e "${YELLOW}► Need elevated privileges for Docker. Using sudo...${NC}"
    sudo $DOCKER_COMPOSE up -d --build
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All services started successfully!${NC}"
    
    echo -e "${BLUE}====================================${NC}"
    echo -e "${GREEN}System is now running!${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "Web app: ${GREEN}http://localhost:8060${NC}"
    echo -e "Flower dashboard: ${GREEN}http://localhost:5555${NC}"
    echo -e "Redis: ${GREEN}localhost:6379${NC}"
    echo -e "R server (direct): ${GREEN}http://localhost:8000${NC}"
    echo -e "R server (original): ${GREEN}http://localhost:8001${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo -e "To view logs: ${YELLOW}docker-compose logs -f${NC}"
    echo -e "To stop: ${YELLOW}./stop_production.sh${NC}"
else
    echo -e "${RED}There was an error starting the services. Check the Docker Compose output above.${NC}"
    exit 1
fi