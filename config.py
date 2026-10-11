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
    """Read a scalar env value with a fallback default."""
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _as_bool(value: str | bool | None, default: bool = False) -> bool:
    """Parse a truthy/falsy env value into a boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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
    # SECRET_KEY and FLASK_SECRET_KEY are accepted interchangeably.
    # In production, missing SECRET_KEY fails fast to prevent insecure sessions.
    SECRET_KEY: str = _env("SECRET_KEY") or _env("FLASK_SECRET_KEY") or _env("SESSION_SECRET")
    if not SECRET_KEY:
        SECRET_KEY = secrets.token_hex(32)
        if IS_PRODUCTION:
            logger.warning(
                "WARNING: No SECRET_KEY set in production environment. "
                "Generated an ephemeral 256-bit secret. "
                "Configure SECRET_KEY in your Render dashboard to persist user sessions across deploys."
            )
        else:
            logger.warning(
                "No FLASK_SECRET_KEY configured — using a random ephemeral secret. "
                "Set FLASK_SECRET_KEY in .env to keep sessions across restarts."
            )

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
    MONGO_CONNECT_TIMEOUT_MS: int = int(_env("MONGO_CONNECT_TIMEOUT_MS", "4000"))

    # DEV ONLY — allows an in-memory mongomock fallback when unreachable.
    # In production, mock fallback is strictly prohibited.
    MONGO_ALLOW_MOCK: bool = False if IS_PRODUCTION else _as_bool(_env("MONGO_ALLOW_MOCK"), default=False)

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
    # Behind HTTPS / cross-origin in production, cookies require SameSite=None and Secure=True.
    SESSION_COOKIE_SECURE: bool = (
        _as_bool(_env("SESSION_COOKIE_SECURE"), default=True)
        if IS_PRODUCTION
        else _as_bool(_env("SESSION_COOKIE_SECURE"), default=False)
    )
    SESSION_COOKIE_SAMESITE: str = (
        _env("SESSION_COOKIE_SAMESITE", "None")
        if IS_PRODUCTION
        else _env("SESSION_COOKIE_SAMESITE", "Lax")
    )
    SESSION_COOKIE_HTTPONLY: bool = True

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