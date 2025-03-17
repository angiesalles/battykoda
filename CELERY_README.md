# BattyCoda Celery Integration

This document explains the new Celery-based asynchronous processing system for BattyCoda.

## Overview

BattyCoda now uses Celery for asynchronous task processing, particularly for generating spectrograms. This provides several benefits:

- **Improved Reliability**: Tasks are now persisted and can be retried if they fail
- **Better Debugging**: Detailed task status and error information
- **Enhanced Performance**: More efficient use of resources, with better concurrency control
- **Scalability**: Workers can be distributed across multiple machines
- **Monitoring**: Real-time task monitoring with Flower

## Architecture

![BattyCoda Celery Architecture](architecture.png)

1. **Flask Web App**: The main application that handles HTTP requests
2. **Celery Tasks**: Defined in `tasks.py`, these contain the actual processing logic
3. **Redis**: The message broker and result backend
4. **Celery Workers**: Processes that execute the tasks asynchronously

## Running the System

### Prerequisites

1. Install Redis (task broker):
   ```bash
   # MacOS
   brew install redis
   brew services start redis
   
   # Linux
   sudo apt install redis-server
   sudo systemctl start redis-server
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Starting Components

1. **Start the Flask App**:
   ```bash
   python main.py
   ```

2. **Start the Celery Worker**:
   ```bash
   ./start_celery_worker.sh
   ```
   
3. **Start Flower (optional, for monitoring)**:
   ```bash
   ./start_flower.sh
   ```
   
4. Access the application at: http://localhost:8060
5. Access Flower monitoring at: http://localhost:5555

## Key Features

### Spectrogram Generation

The spectrogram endpoint now has these capabilities:

1. **Immediate Responses**: If the spectrogram already exists, it's served directly
2. **Asynchronous Generation**: If not, a Celery task is created and can be processed asynchronously
3. **Pre-fetching**: Can proactively generate spectrograms that will likely be needed soon

### Task Tracking

New endpoints are available for tracking task status:

- `/status/task/<task_id>`: Shows the status of a specific task
- `/debug/celery_status`: Shows the status of the Celery system

### Async Mode

Add `?async=true` to spectrogram requests to get an immediate response with a task ID rather than waiting for generation.

Example:
```
GET /spectrogram?wav_path=home/user/audio.wav&hash=123456&call=0&channel=0&overview=0&contrast=0.5&numcalls=42&async=true
```

Response:
```json
{
  "status": "queued",
  "task_id": "7c2f7ea1-f8c8-4c17-b8d0-4f8e6ad985f2",
  "poll_url": "/status/task/7c2f7ea1-f8c8-4c17-b8d0-4f8e6ad985f2"
}
```

### Pre-fetching

Add `?prefetch=true` to have the system proactively generate the next few spectrograms in a sequence:

Example:
```
GET /spectrogram?wav_path=home/user/audio.wav&hash=123456&call=0&channel=0&overview=0&contrast=0.5&numcalls=42&prefetch=true
```

## Configuration

Celery configuration can be set through environment variables:

- `CELERY_BROKER_URL`: Redis URL for the message broker (default: redis://localhost:6379/0)
- `CELERY_RESULT_BACKEND`: Redis URL for the result backend (default: redis://localhost:6379/0)

## Troubleshooting

1. **Tasks not executing**: Check if Redis is running: `redis-cli ping` should return `PONG`
2. **Flower not showing tasks**: Make sure you're using the same Redis server for all components
3. **Task failures**: Check the worker logs for detailed error information

## Architecture Diagram 

```
┌────────────────┐          ┌─────────────────┐          ┌───────────────┐
│                │          │                 │          │               │
│  Flask Web App │◄────────►│ Redis (Broker)  │◄────────►│ Celery Worker │
│                │          │                 │          │               │
└───────┬────────┘          └─────────────────┘          └───────┬───────┘
        │                                                        │
        │                                                        │
        │                                                        │
        │                                                        │
        ▼                                                        ▼
┌────────────────┐                                     ┌───────────────────┐
│                │                                     │                   │
│  Web Browser   │                                     │  Generated Files  │
│                │                                     │                   │
└────────────────┘                                     └───────────────────┘
```