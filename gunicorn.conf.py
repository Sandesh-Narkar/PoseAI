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


def on_starting(server):
    """Ensure a unified SECRET_KEY is set in the master process before workers fork."""
    import secrets
    from pathlib import Path

    if not os.environ.get("SECRET_KEY"):
        secret_file = Path(__file__).resolve().parent / "data" / ".secret_key"
        try:
            if secret_file.exists():
                stored = secret_file.read_text(encoding="utf-8").strip()
                if stored and len(stored) >= 16:
                    os.environ["SECRET_KEY"] = stored
                    return
            secret_file.parent.mkdir(parents=True, exist_ok=True)
            new_key = secrets.token_hex(32)
            secret_file.write_text(new_key, encoding="utf-8")
            os.environ["SECRET_KEY"] = new_key
        except Exception:
            os.environ["SECRET_KEY"] = secrets.token_hex(32)

