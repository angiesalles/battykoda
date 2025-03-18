#!/bin/bash
# Script to restrict server access to only Cloudflare IPs
# This helps ensure all traffic passes through Cloudflare

# Set up colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}Setting up Cloudflare-only Firewall${NC}"
echo -e "${BLUE}====================================${NC}"

# Check if script is run with sudo
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run this script with sudo privileges${NC}"
  exit 1
fi

# Create temporary directory
mkdir -p /tmp/cloudflare_ips

# Download latest Cloudflare IP ranges
echo -e "${YELLOW}► Downloading Cloudflare IP ranges...${NC}"
curl -s https://www.cloudflare.com/ips-v4 -o /tmp/cloudflare_ips/cf_ips_v4
curl -s https://www.cloudflare.com/ips-v6 -o /tmp/cloudflare_ips/cf_ips_v6

if [ ! -s /tmp/cloudflare_ips/cf_ips_v4 ] || [ ! -s /tmp/cloudflare_ips/cf_ips_v6 ]; then
  echo -e "${RED}Failed to download Cloudflare IP ranges${NC}"
  exit 1
fi

# Save the existing iptables rules
echo -e "${YELLOW}► Backing up current iptables rules...${NC}"
iptables-save > /tmp/cloudflare_ips/iptables_backup
ip6tables-save > /tmp/cloudflare_ips/ip6tables_backup

# First, clear any existing ACCEPT or DROP rules for web ports
echo -e "${YELLOW}► Clearing existing web port rules...${NC}"
# IPv4
iptables -D INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null
iptables -D INPUT -p tcp --dport 8000 -j ACCEPT 2>/dev/null
iptables -D INPUT -p tcp --dport 8060 -j ACCEPT 2>/dev/null
iptables -D INPUT -p tcp --dport 8080 -j ACCEPT 2>/dev/null
iptables -D INPUT -p tcp --dport 80 -j DROP 2>/dev/null
iptables -D INPUT -p tcp --dport 8000 -j DROP 2>/dev/null
iptables -D INPUT -p tcp --dport 8060 -j DROP 2>/dev/null
iptables -D INPUT -p tcp --dport 8080 -j DROP 2>/dev/null
# IPv6
ip6tables -D INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8000 -j ACCEPT 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8060 -j ACCEPT 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8080 -j ACCEPT 2>/dev/null
ip6tables -D INPUT -p tcp --dport 80 -j DROP 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8000 -j DROP 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8060 -j DROP 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8080 -j DROP 2>/dev/null

# Create a new iptables chain for Cloudflare
echo -e "${YELLOW}► Creating Cloudflare iptables chains...${NC}"
iptables -F CLOUDFLARE 2>/dev/null || iptables -N CLOUDFLARE
ip6tables -F CLOUDFLARE 2>/dev/null || ip6tables -N CLOUDFLARE

# Allow connections from Cloudflare IP ranges to web ports
echo -e "${YELLOW}► Adding Cloudflare IP ranges to allowed list...${NC}"
for ip in $(cat /tmp/cloudflare_ips/cf_ips_v4); do
  echo -e "${BLUE}  Adding IPv4 range: ${ip}${NC}"
  # Standard HTTP port
  iptables -A CLOUDFLARE -s $ip -p tcp --dport 80 -j ACCEPT
  # Django development server port
  iptables -A CLOUDFLARE -s $ip -p tcp --dport 8000 -j ACCEPT
  # Battycoda web port
  iptables -A CLOUDFLARE -s $ip -p tcp --dport 8060 -j ACCEPT
  # Gunicorn port if used
  iptables -A CLOUDFLARE -s $ip -p tcp --dport 8080 -j ACCEPT
done

for ip in $(cat /tmp/cloudflare_ips/cf_ips_v6); do
  echo -e "${BLUE}  Adding IPv6 range: ${ip}${NC}"
  # Standard HTTP port
  ip6tables -A CLOUDFLARE -s $ip -p tcp --dport 80 -j ACCEPT
  # Django development server port
  ip6tables -A CLOUDFLARE -s $ip -p tcp --dport 8000 -j ACCEPT
  # Battycoda web port
  ip6tables -A CLOUDFLARE -s $ip -p tcp --dport 8060 -j ACCEPT
  # Gunicorn port if used
  ip6tables -A CLOUDFLARE -s $ip -p tcp --dport 8080 -j ACCEPT
done

# Remove any existing rules for the CLOUDFLARE chain first
echo -e "${YELLOW}► Cleaning up existing chain references...${NC}"
iptables -D INPUT -p tcp --dport 80 -j CLOUDFLARE 2>/dev/null
iptables -D INPUT -p tcp --dport 8000 -j CLOUDFLARE 2>/dev/null
iptables -D INPUT -p tcp --dport 8060 -j CLOUDFLARE 2>/dev/null
iptables -D INPUT -p tcp --dport 8080 -j CLOUDFLARE 2>/dev/null
ip6tables -D INPUT -p tcp --dport 80 -j CLOUDFLARE 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8000 -j CLOUDFLARE 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8060 -j CLOUDFLARE 2>/dev/null
ip6tables -D INPUT -p tcp --dport 8080 -j CLOUDFLARE 2>/dev/null

# Insert the CLOUDFLARE chain into the INPUT chain
echo -e "${YELLOW}► Configuring iptables to use Cloudflare chain...${NC}"
iptables -I INPUT -p tcp --dport 80 -j CLOUDFLARE
iptables -I INPUT -p tcp --dport 8000 -j CLOUDFLARE
iptables -I INPUT -p tcp --dport 8060 -j CLOUDFLARE
iptables -I INPUT -p tcp --dport 8080 -j CLOUDFLARE
ip6tables -I INPUT -p tcp --dport 80 -j CLOUDFLARE
ip6tables -I INPUT -p tcp --dport 8000 -j CLOUDFLARE
ip6tables -I INPUT -p tcp --dport 8060 -j CLOUDFLARE
ip6tables -I INPUT -p tcp --dport 8080 -j CLOUDFLARE

# Block all other traffic to web ports
echo -e "${YELLOW}► Blocking non-Cloudflare traffic to web ports...${NC}"
iptables -A INPUT -p tcp --dport 80 -j DROP
iptables -A INPUT -p tcp --dport 8000 -j DROP
iptables -A INPUT -p tcp --dport 8060 -j DROP
iptables -A INPUT -p tcp --dport 8080 -j DROP
ip6tables -A INPUT -p tcp --dport 80 -j DROP
ip6tables -A INPUT -p tcp --dport 8000 -j DROP
ip6tables -A INPUT -p tcp --dport 8060 -j DROP
ip6tables -A INPUT -p tcp --dport 8080 -j DROP

# Always allow SSH, otherwise you might lock yourself out
echo -e "${YELLOW}► Ensuring SSH access is preserved...${NC}"
iptables -I INPUT -p tcp --dport 22 -j ACCEPT
ip6tables -I INPUT -p tcp --dport 22 -j ACCEPT

# Allow local traffic
echo -e "${YELLOW}► Allowing local network traffic...${NC}"
iptables -I INPUT -i lo -j ACCEPT
ip6tables -I INPUT -i lo -j ACCEPT

# Allow established connections
echo -e "${YELLOW}► Allowing established connections...${NC}"
iptables -I INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
ip6tables -I INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

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
  echo -e "${YELLOW}► Or manually save rules and create a startup script${NC}"
fi

echo -e "${GREEN}✓ Firewall configured successfully!${NC}"
echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}Your web server is now configured to only accept connections from Cloudflare's IP ranges${NC}"
echo -e "${YELLOW}Note: If Cloudflare updates their IP ranges, you'll need to run this script again${NC}"
echo -e "${BLUE}====================================${NC}"

# Display current ruleset
echo -e "${YELLOW}Current iptables rules:${NC}"
iptables -L INPUT -n --line-numbers

# Add test command to check if the rule works
echo -e "${YELLOW}To test if your IP is blocked, try:${NC}"
echo -e "${BLUE}  curl -v http://$(hostname -I | awk '{print $1}'):8060${NC}"

# Ask to restore in case of problem
echo -e "${YELLOW}If you encounter any issues and want to restore the previous firewall rules, run:${NC}"
echo -e "${BLUE}  sudo iptables-restore < /tmp/cloudflare_ips/iptables_backup${NC}"
echo -e "${BLUE}  sudo ip6tables-restore < /tmp/cloudflare_ips/ip6tables_backup${NC}"

# Also mention the removal script
echo -e "${YELLOW}To remove these firewall rules completely, run:${NC}"
echo -e "${BLUE}  sudo bash /home/ubuntu/battycoda/remove_cloudflare_firewall.sh${NC}"