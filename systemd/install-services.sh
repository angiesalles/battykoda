#!/bin/bash
# Install BattyCoda systemd services

# Set up colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Installing BattyCoda systemd services${NC}"
echo -e "${BLUE}====================================${NC}"

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root (sudo)${NC}"
    exit 1
fi

# Create directory if it doesn't exist
mkdir -p /home/ubuntu/battycoda/systemd

# Copy service files to systemd directory
echo -e "${YELLOW}► Copying service files to systemd directory...${NC}"
cp /home/ubuntu/battycoda/systemd/*.service /etc/systemd/system/

# Reload systemd
echo -e "${YELLOW}► Reloading systemd daemon...${NC}"
systemctl daemon-reload

# Enable services
echo -e "${YELLOW}► Enabling services...${NC}"
systemctl enable battycoda-web.service
systemctl enable battycoda-celery.service
systemctl enable battycoda-flower.service
systemctl enable battycoda-r-direct.service
systemctl enable battycoda-r-original.service

# Check for required dependencies
echo -e "${YELLOW}► Checking for dependencies...${NC}"

# Check for gunicorn
if ! command -v gunicorn &> /dev/null; then
    echo -e "${YELLOW}Installing gunicorn...${NC}"
    pip install gunicorn
fi

# Check for redis
if ! systemctl status redis &> /dev/null; then
    echo -e "${YELLOW}Installing redis...${NC}"
    apt-get update
    apt-get install -y redis-server
    systemctl enable redis
    systemctl start redis
fi

echo -e "${GREEN}✓ Services installed successfully!${NC}"
echo -e "${YELLOW}To start all services: ${NC}sudo systemctl start battycoda-web battycoda-celery battycoda-flower battycoda-r-direct battycoda-r-original"
echo -e "${YELLOW}To stop all services: ${NC}sudo systemctl stop battycoda-web battycoda-celery battycoda-flower battycoda-r-direct battycoda-r-original"
echo -e "${YELLOW}To check status: ${NC}sudo systemctl status battycoda-*"
echo -e "${YELLOW}To view logs: ${NC}sudo journalctl -u battycoda-web"