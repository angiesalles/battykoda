#!/bin/bash
# Script to remove Cloudflare-only firewall rules and allow direct access

# Set up colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Removing Cloudflare-only Firewall${NC}"
echo -e "${BLUE}====================================${NC}"

# Check if script is run with sudo
if [ "$(id -u)" -ne 0 ]; then
  echo -e "${RED}Please run this script with sudo privileges${NC}"
  exit 1
fi

# Remove the DROP rules for non-Cloudflare traffic
echo -e "${YELLOW}► Removing DROP rules for web ports...${NC}"
iptables -D INPUT -p tcp --dport 80 -j DROP 2>/dev/null
iptables -D INPUT -p tcp --dport 8060 -j DROP 2>/dev/null
ip6tables -D INPUT -p tcp --dport 80 -j DROP 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8060 -j DROP 2>/dev/null

# Remove the Cloudflare chain references
echo -e "${YELLOW}► Removing Cloudflare chain references...${NC}"
iptables -D INPUT -p tcp --dport 80 -j CLOUDFLARE 2>/dev/null
iptables -D INPUT -p tcp --dport 8060 -j CLOUDFLARE 2>/dev/null
ip6tables -D INPUT -p tcp --dport 80 -j CLOUDFLARE 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8060 -j CLOUDFLARE 2>/dev/null

# Allow all traffic on web ports
echo -e "${YELLOW}► Allowing all traffic to web ports...${NC}"
iptables -I INPUT -p tcp --dport 80 -j ACCEPT
iptables -I INPUT -p tcp --dport 8060 -j ACCEPT
ip6tables -I INPUT -p tcp --dport 80 -j ACCEPT
ip6tables -I INPUT -p tcp --dport 8060 -j ACCEPT

# Making the rules persistent
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
fi

echo -e "${GREEN}✓ Firewall rules removed successfully!${NC}"
echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}Your web server now accepts direct connections on ports 80 and 8060${NC}"
echo -e "${BLUE}====================================${NC}"