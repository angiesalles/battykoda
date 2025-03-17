#!/bin/bash
# Script to easily monitor logs for the BattyCoda system

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

# Function to show usage
usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo -e "  ${GREEN}./view_logs.sh${NC} ${YELLOW}<component>${NC}"
    echo -e ""
    echo -e "${BLUE}Components:${NC}"
    echo -e "  ${YELLOW}flask${NC}     - View Flask app logs"
    echo -e "  ${YELLOW}celery${NC}    - View Celery worker logs"
    echo -e "  ${YELLOW}flower${NC}    - View Flower logs"
    echo -e "  ${YELLOW}all${NC}       - View all logs in split panes (requires tmux)"
    echo -e ""
    echo -e "${BLUE}Examples:${NC}"
    echo -e "  ${GREEN}./view_logs.sh flask${NC}    # View Flask logs"
    echo -e "  ${GREEN}./view_logs.sh all${NC}      # View all logs in split panes"
    exit 1
}

# Check if component was specified
if [ $# -lt 1 ]; then
    usage
fi

COMPONENT=$1

case $COMPONENT in
    "flask")
        echo -e "${GREEN}Viewing Flask app logs (press Ctrl+C to exit)${NC}"
        tail -f logs/flask_app.log
        ;;
    "celery")
        echo -e "${GREEN}Viewing Celery worker logs (press Ctrl+C to exit)${NC}"
        tail -f logs/celery_worker.log
        ;;
    "flower")
        echo -e "${GREEN}Viewing Flower logs (press Ctrl+C to exit)${NC}"
        tail -f logs/flower.log
        ;;
    "all")
        # Check if tmux is installed
        if ! command -v tmux &> /dev/null; then
            echo -e "${RED}Error: tmux is not installed.${NC}"
            echo -e "${YELLOW}Please install tmux to use the 'all' option:${NC}"
            echo -e "  - On macOS: ${GREEN}brew install tmux${NC}"
            echo -e "  - On Linux: ${GREEN}sudo apt install tmux${NC}"
            exit 1
        fi
        
        echo -e "${GREEN}Starting tmux session with all logs (press Ctrl+B then D to detach)${NC}"
        # Kill any existing session with the same name
        tmux kill-session -t battykoda_logs 2>/dev/null || true
        
        # Create a new session
        tmux new-session -d -s battykoda_logs "echo -e '${BLUE}Flask App Logs${NC}'; tail -f logs/flask_app.log"
        
        # Split horizontally and run Celery logs
        tmux split-window -h -t battykoda_logs "echo -e '${BLUE}Celery Worker Logs${NC}'; tail -f logs/celery_worker.log"
        
        # Split the right pane vertically and run Flower logs on the bottom
        tmux split-window -v -t battykoda_logs:0.1 "echo -e '${BLUE}Flower Logs${NC}'; tail -f logs/flower.log"
        
        # Attach to the session
        tmux attach-session -t battykoda_logs
        ;;
    *)
        echo -e "${RED}Error: Unknown component '${COMPONENT}'${NC}"
        usage
        ;;
esac