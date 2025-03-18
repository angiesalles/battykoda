#!/bin/bash
# Script to set up port forwarding from port 80 to port 8060

# Set up colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Setting up Port Forwarding (80 → 8060)${NC}"
echo -e "${BLUE}====================================${NC}"

# Check if script is run with sudo
if [ "$(id -u)" -ne 0 ]; then
  echo -e "${RED}Please run this script with sudo privileges${NC}"
  exit 1
fi

# First remove any existing rules
echo -e "${YELLOW}► Removing any existing port forwarding rules...${NC}"
iptables -t nat -D PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8060 2>/dev/null
iptables -t nat -D OUTPUT -p tcp --dport 80 -j REDIRECT --to-port 8060 2>/dev/null

# Add port forwarding rules
echo -e "${YELLOW}► Adding port forwarding rules...${NC}"
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8060
iptables -t nat -A OUTPUT -p tcp -o lo --dport 80 -j REDIRECT --to-port 8060

# Making the rules persistent (works on Ubuntu and Debian)
if command -v netfilter-persistent &> /dev/null; then
  echo -e "${YELLOW}► Making iptables rules persistent...${NC}"
  netfilter-persistent save
elif [ -d "/etc/iptables" ]; then
  echo -e "${YELLOW}► Saving iptables rules to /etc/iptables/...${NC}"
  iptables-save > /etc/iptables/rules.v4
  ip6tables-save > /etc/iptables/rules.v6
else
  echo -e "${YELLOW}► To make these rules persistent, install iptables-persistent:${NC}"
  echo -e "${YELLOW}  sudo apt-get install iptables-persistent${NC}"
  echo -e "${YELLOW}► Or you can add this script to crontab to run at every boot:${NC}"
  echo -e "${YELLOW}  @reboot /path/to/setup_port_forward.sh${NC}"
fi

echo -e "${GREEN}✓ Port forwarding configured successfully!${NC}"
echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}Requests to port 80 will be forwarded to port 8060${NC}"
echo -e "${GREEN}Both local and external connections will work${NC}"
echo -e "${BLUE}====================================${NC}"