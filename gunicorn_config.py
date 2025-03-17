"""Gunicorn configuration file for BattyCoda"""

import multiprocessing
import os

# Bind to 0.0.0.0:8060 by default, but allow overrides from environment
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8060")

# Use the number of CPU cores for worker processes
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# Set worker class to handle async tasks better
worker_class = "gevent"

# Timeout for worker processes (increase if you have long-running tasks)
timeout = 120

# Add more resilient settings
keepalive = 5
worker_connections = 1000
graceful_timeout = 30

# Handle connection issues more gracefully
forwarded_allow_ips = '*'
proxy_protocol = True
proxy_allow_ips = '*'

# Restart workers after serving this many requests
max_requests = 1000
max_requests_jitter = 50

# Log settings
logfile = "logs/gunicorn.log"
loglevel = "info"
accesslog = "logs/access.log"
errorlog = "logs/error.log"

# Security settings - prevent server info disclosure
proc_name = "battycoda"
secure_scheme_headers = {"X-FORWARDED-PROTOCOL": "https", "X-FORWARDED-PROTO": "https", "X-FORWARDED-SSL": "on"}

# Enable post-fork hooks
def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def on_exit(server):
    server.log.info("Shutting down gunicorn application")
