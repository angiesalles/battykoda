# BattyKoda Development Guide

This guide explains how to run BattyKoda in development mode with auto-reload.

## Development Server

### Running in the Foreground

To run the development server in the foreground (recommended for active development):

```bash
./run_dev.sh
```

This will:
- Activate the virtual environment (if it exists)
- Start the Flask server with debug mode and auto-reload enabled
- Print helpful information about accessing the server

You'll see all server output in your terminal, and you can stop the server by pressing `Ctrl+C`.

### Running in the Background

To run the development server in the background:

```bash
./run_dev_bg.sh
```

This will:
- Start the server in the background
- Write logs to `battykoda_dev.log`
- Print information about accessing the server and viewing logs

### Viewing Server Logs

To view the logs when running in background mode:

```bash
./view_logs.sh
```

### Stopping the Background Server

To stop the background server:

```bash
./stop_dev.sh
```

## Auto-Reload Feature

When running in development mode, the server will automatically restart whenever a Python file is changed. This allows you to:

1. Edit code
2. Save the file
3. See changes immediately without manually restarting the server

### What Changes Trigger Auto-Reload?

- Changes to `.py` files in the project
- Changes to templates in the `templates/` directory

### What Doesn't Trigger Auto-Reload?

- Changes to static files (need to refresh browser)
- Database changes (if any)
- Configuration files (restart server manually)

## Accessing the Application

Once the server is running, you can access BattyKoda at:

- http://127.0.0.1:8060
- http://localhost:8060

## Troubleshooting

If the server doesn't start or auto-reload doesn't work:

1. Make sure you have the required Python packages installed (Flask, etc.)
2. Check if there's already a server running (port 8060 might be in use)
3. Check the logs for specific error messages
4. Kill any orphaned processes with `pkill -f "python3 dev_server.py"`

## R Integration

BattyKoda now uses R for bat call classification through the `classify_call.R` script. This provides more accurate classifications than the Python-only implementation.

### Requirements

To use the R integration:

1. Install R (version 4.0+ recommended)
2. Install required R packages (see R_REQUIREMENTS.md)
3. Ensure R executable is in your PATH

### How it Works

1. When a bat call needs to be classified, Python calls the R script:
   ```
   Rscript classify_call.R <wav_file_path> <onset_time> <offset_time> [species]
   ```

2. The R script extracts acoustic features from the call and determines:
   - Call type (Echo, FM, Social, etc.)
   - Confidence score (0-100%)

3. The R script outputs results in a standardized format:
   ```
   type: 'Echo'
   confidence: 75.5
   ```

4. Python parses these results and uses them in the application

### Error Handling

If R is unavailable or fails, BattyKoda will default to basic 'Echo' classification with a neutral confidence score of 50%.

### Debugging R Integration

If you encounter issues with the R integration:

1. Check the Python logs for R execution errors
2. Test the R script directly from command line
3. Verify that all required R packages are installed
4. Set `R = False` in GetTask.py to temporarily disable R integration