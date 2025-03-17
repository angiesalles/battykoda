# BattyCoda R Server Setup

This document describes the R server setup for bat call classification in BattyCoda.

## Overview

BattyCoda uses R for bat call classification through acoustic feature extraction and machine learning. Two different R server implementations are provided:

1. **Direct KNN Server (Primary)** - A simplified implementation that bypasses mlr3 compatibility issues by using the standard R `class` package's `knn` function directly.
   - Default port: 8000
   - Implementation: `r_server_direct.R`
   - Advantages: More reliable across different R/mlr3 versions, simpler code

2. **Original Server (Backup)** - The original implementation that uses the mlr3 framework.
   - Default port: 8001
   - Implementation: `r_prediction_server.R`
   - Advantages: Uses the full mlr3 framework, potentially more accurate

The system is configured to try both servers in order, with fallbacks to direct script execution if needed, ensuring maximum reliability.

## System Components

### R Scripts

- **r_server_direct.R** - Direct KNN implementation that avoids mlr3 dependency issues
- **r_prediction_server.R** - Original implementation using mlr3
- **direct_kknn_simple.R** - Standalone function for direct classification (useful for testing)
- **classify_call.R** - Legacy script for direct subprocess execution

### Management Scripts

- **start_system.sh** - Starts both R servers, along with other system components
- **stop_system.sh** - Stops both R servers (respects RStudio sessions)
- **start_r_servers.sh** - Starts only the R servers (for debugging purposes)
- **check_system.sh** - Checks the status of all system components, including R servers

## API Endpoints

Both servers expose the same API endpoints:

- `GET /ping` - Check server status
- `POST /classify` - Classify a bat call
  - Parameters:
    - `wav_path` - Path to the WAV file
    - `onset` - Start time in seconds
    - `offset` - End time in seconds
    - `species` - Bat species (default: "Efuscus")
- `GET /call_types` - Get available call types for a species
- `GET /debug/model` - Get model information (debug mode only)

## Starting the Servers

The R servers are automatically started when you run `./start_system.sh`. If you want to start only the R servers, you can run:

```bash
./start_r_servers.sh
```

## Checking Server Status

You can check the status of both R servers by running:

```bash
./check_system.sh
```

This will show if both servers are running, on which ports, and if they are responsive.

## Testing the Servers

You can test the servers directly using curl:

```bash
# Test the direct KNN server
curl http://localhost:8000/ping

# Test the original server
curl http://localhost:8001/ping

# Test classification
curl -X POST http://localhost:8000/classify \
  -d "wav_path=/path/to/bat_call.wav" \
  -d "onset=0.1" \
  -d "offset=0.3" \
  -d "species=Efuscus"
```

## Troubleshooting

### Server Won't Start

If the R servers won't start:

1. Check if R is installed: `R --version`
2. Check if required packages are installed: `Rscript -e "library(plumber); library(class)"`
3. Check the log files:
   - Direct KNN server: `logs/r_server_direct.log`
   - Original server: `logs/r_server_original.log`

### Port Conflicts

If there's a port conflict (e.g., RStudio is using port 8000), the system will automatically try to use alternative ports:

- Direct KNN server: Port 8002 instead of 8000
- Original server: No alternative port (will not start)

You can check which ports are in use with:

```bash
lsof -i :8000  # Check port 8000
lsof -i :8001  # Check port 8001
lsof -i :8002  # Check port 8002
```

## Performance and Reliability

The direct KNN implementation (port 8000) is the primary server and should be used when possible. It's more reliable across different R/mlr3 versions.

The original implementation (port 8001) is provided as a backup and for compatibility with existing code.

The Python code in `task_management/audio_processing.py` is configured to try both servers in order, ensuring maximum reliability.

## RStudio Integration

Both servers can be run from RStudio for interactive debugging. The system will automatically detect and preserve RStudio sessions on port 8000.