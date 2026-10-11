"""
PoseAI — Application Configuration

Single source of configuration for the Flask backend. Values are read
from environment variables, with the local `.env` file loaded
automatically via python-dotenv (see .env.example for the full list of
supported variables).

Consumers:
    - app.py                       (Flask app config / CORS / sessions)
    - auth.py                      (secret, Google OAuth, rate limiting, HIBP)
    - database/mongo.py            (MongoDB connection + mock fallback)
    - database/workouts.py         (workout persistence)
    - nutrition/                   (vision / OCR / USDA / Gemini APIs)
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger("poseai.config")

# Load the .env file next to this module (if present). Existing process
# environment variables always take precedence over the file.
_ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_FILE, override=False)


def _env(key: str, default: str = "") -> str:
    """Read a scalar env value with a fallback default, stripping whitespace and quotes."""
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    return value.strip().strip("'").strip('"')


def _as_bool(value: str | bool | None, default: bool = False) -> bool:
    """Parse a truthy/falsy env value into a boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_secret_key() -> str:
    """Resolve a stable, persistent secret key for Flask sessions across Gunicorn workers and restarts."""
    env_key = _env("SECRET_KEY") or _env("FLASK_SECRET_KEY") or _env("SESSION_SECRET")
    if env_key:
        return env_key

    # Persist the generated secret to data/.secret_key so all Gunicorn workers share the exact same key
    secret_file = Path(__file__).resolve().parent / "data" / ".secret_key"
    try:
        if secret_file.exists():
            stored = secret_file.read_text(encoding="utf-8").strip()
            if stored and len(stored) >= 16:
                return stored
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        new_key = secrets.token_hex(32)
        secret_file.write_text(new_key, encoding="utf-8")
        logger.info("Persisted stable SECRET_KEY to %s for cross-worker session sharing.", secret_file)
        return new_key
    except Exception as exc:
        logger.warning("Could not persist secret key to disk (%s); generating in-memory key.", exc)
        return secrets.token_hex(32)


class Config:
    """Base configuration, populated from the environment / .env file."""

    # ── Environment mode ─────────────────────────────────────────────
    ENVIRONMENT: str = _env(
        "APP_ENV",
        _env("ENVIRONMENT", _env("NODE_ENV", _env("FLASK_ENV", "development"))),
    ).lower()
    IS_PRODUCTION: bool = ENVIRONMENT in {"production", "prod"} or bool(os.getenv("RENDER"))
    PORT: int = int(_env("PORT", "5000"))

    # ── Flask / session secret ───────────────────────────────────────
    # SECRET_KEY is stable across all Gunicorn workers via _resolve_secret_key
    SECRET_KEY: str = _resolve_secret_key()

    # ── MongoDB (Atlas in production, local/mock fallback in dev) ─────
    # MONGODB_URI and MONGO_URI are accepted interchangeably.
    MONGO_URI: str = _env("MONGODB_URI") or _env("MONGO_URI")
    if not MONGO_URI:
        if IS_PRODUCTION:
            logger.warning(
                "WARNING: MONGODB_URI is not set in production. "
                "Configure MONGODB_URI in your Render dashboard to connect to MongoDB Atlas."
            )
        MONGO_URI = "mongodb://127.0.0.1:27017"

    MONGODB_URI: str = MONGO_URI
    MONGO_DB_NAME: str = _env("MONGODB_DATABASE") or _env("MONGO_DB_NAME", "poseai")
    MONGODB_DATABASE: str = MONGO_DB_NAME
    MONGO_CONNECT_TIMEOUT_MS: int = int(_env("MONGO_CONNECT_TIMEOUT_MS", "8000"))

    # Allows fallback if real MongoDB is unreachable, preventing authentication downtime.
    # Set MONGO_ALLOW_MOCK=0 in Render if you strictly require hard rejection on DB outage.
    _mock_env = os.getenv("MONGO_ALLOW_MOCK")
    MONGO_ALLOW_MOCK: bool = _as_bool(_mock_env, default=True) if _mock_env is not None else True

    # ── Cross-origin resource sharing ────────────────────────────────
    # Supports FRONTEND_URL, ALLOWED_ORIGINS, or legacy CORS_ORIGINS.
    # In production, wildcards are disallowed to protect credentialed requests.
    FRONTEND_URL: str = _env("FRONTEND_URL")
    ALLOWED_ORIGINS: str = (
        _env("ALLOWED_ORIGINS")
        or _env("CORS_ORIGINS")
        or FRONTEND_URL
        or ("" if IS_PRODUCTION else "*")
    )
    CORS_ORIGINS: str = ALLOWED_ORIGINS

    # ── Session cookie security ──────────────────────────────────────
    # Stable first-party cookie configuration so login/signup sessions persist reliably across page loads
    SESSION_COOKIE_NAME: str = "poseai_session"
    SESSION_COOKIE_PATH: str = "/"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = _env("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE: bool = (
        _as_bool(_env("SESSION_COOKIE_SECURE"), default=True)
        if IS_PRODUCTION
        else False
    )
    PERMANENT_SESSION_LIFETIME: int = int(_env("PERMANENT_SESSION_LIFETIME", "604800"))  # 7 days

    # ── Rate limiting (login/signup) ─────────────────────────────────
    RATELIMIT_STORAGE_URI: str = _env("RATELIMIT_STORAGE_URI", "memory://")
    RATE_LIMIT_ENABLED: bool = _as_bool(_env("RATE_LIMIT_ENABLED"), default=False)

    # ── Google OAuth 2.0 ─────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = _env("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = _env("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = _env(
        "GOOGLE_REDIRECT_URI", "http://127.0.0.1:5000/auth/google/callback"
    )
    # Local-only dev stub that signs in a synthetic Google identity.
    GOOGLE_OAUTH_DEV_MODE: bool = _as_bool(_env("GOOGLE_OAUTH_DEV_MODE"), default=False)
    GOOGLE_DEV_EMAIL: str = _env("GOOGLE_DEV_EMAIL", "google.dev@example.com")
    GOOGLE_DEV_NAME: str = _env("GOOGLE_DEV_NAME", "Google Dev Athlete")

    # ── Gemini 2.5 Flash & USDA Food APIs (Optional / graceful) ───────
    GEMINI_API_KEY: str = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
    USDA_API_KEY: str = _env("USDA_API_KEY")

    # ── Password breach checking (Have I Been Pwned, k-anonymity) ────
    HIBP_CHECK_ENABLED: bool = _as_bool(_env("HIBP_CHECK_ENABLED"), default=True)

    # ── Workout / statistics persistence (legacy SQLAlchemy target) ──
    DATABASE_URL: str = _env("DATABASE_URL", "sqlite:///poseai.db")

    # ── CSRF / WTF forms – enabled by default, tests may override ────
    WTF_CSRF_ENABLED: bool = _as_bool(_env("WTF_CSRF_ENABLED"), default=True)
    WTF_CSRF_CHECK_DEFAULT: bool = _as_bool(_env("WTF_CSRF_CHECK_DEFAULT"), default=False)

    # ── Testing flag (never inherited from env, set by test suites) ──
    TESTING: bool = False