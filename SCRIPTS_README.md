# BattyCoda Control Scripts

This document explains the control scripts provided for managing the BattyCoda system.

## Overview

These scripts provide a simple way to manage the different components of the BattyCoda system, including Flask, Celery, and Redis.

## Available Scripts

### System Control

- **`./start_system.sh`** - Start all components (Redis, Celery worker, Flower, Flask app)
- **`./stop_system.sh`** - Stop all components (except Redis by default)
  - Use `./stop_system.sh --stop-redis` to also stop Redis
- **`./refresh_system.sh`** - Restart the entire system (useful after code changes)
  - Use `./refresh_system.sh --clean-cache` to also clear Redis cache

### Monitoring

- **`./check_system.sh`** - Check the health of all system components
- **`./view_logs.sh`** - View logs of different components
  - `./view_logs.sh flask` - View Flask app logs
  - `./view_logs.sh celery` - View Celery worker logs  
  - `./view_logs.sh flower` - View Flower monitoring logs
  - `./view_logs.sh all` - View all logs in tmux split panes (requires tmux)

## Common Workflows

### Starting from scratch

```bash
# Install Redis first (if not already installed)
# On macOS: brew install redis
# On Linux: sudo apt install redis-server

# Install Python dependencies
pip install -r requirements.txt

# Start the system
./start_system.sh
```

### After making code changes

```bash
# Refresh the system
./refresh_system.sh
```

### When finished working

```bash
# Stop all components except Redis
./stop_system.sh

# Or, to stop everything including Redis
./stop_system.sh --stop-redis
```

### Debugging

```bash
# Check system health
./check_system.sh

# View Flask logs
./view_logs.sh flask

# View all logs in split panes (requires tmux)
./view_logs.sh all

# Access Flower dashboard
open http://localhost:5555
```

## Directory Structure

The system creates several directories to organize its files:

- **`logs/`** - Contains log files for all components
  - `flask_app.log` - Flask application logs
  - `celery_worker.log` - Celery worker logs
  - `flower.log` - Flower monitoring logs

## Notes

1. Redis must be installed on your system for the Celery components to work.
2. The scripts use `.flask.pid` to track the Flask app process ID.
3. Always use these scripts for managing the system to ensure proper startup and shutdown.
4. Using `./view_logs.sh all` requires tmux to be installed:
   - On macOS: `brew install tmux`
   - On Linux: `sudo apt install tmux`