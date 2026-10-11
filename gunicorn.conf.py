"""
PoseAI — Gunicorn Production Configuration
Automatically loaded by Gunicorn on startup, ensuring the application
listens on 0.0.0.0:$PORT even if the start command is simply 'gunicorn app:app'.
"""

import os

# Port assigned dynamically by Render or local environment
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Concurrency & threading
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))

# Stream logs to stdout / stderr for Render log viewer
accesslog = "-"
errorlog = "-"
loglevel = "info"
