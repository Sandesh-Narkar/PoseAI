"""
core/session_manager.py
-----------------------
Centralised WebWorkoutEngine registry.

Extracted from app.py so that both app.py and dashboard_api.py can
access the per-user engine dictionary without creating a circular
import (app.py imports dashboard_api.py as a blueprint; if
dashboard_api.py imported from app.py we would get a circular
dependency).

Engines are created lazily: the first time a user (identified by the
Flask session user_id) makes a workout request, a fresh
WebWorkoutEngine is constructed and stored here. Subsequent requests
from the same user re-use the same engine instance, preserving all
live session state (reps, stage, smoother, etc.).

Unauthenticated callers (the legacy desktop main.py bridge that POSTs
to /api/update) share a single "default" engine that is never keyed
to a user.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("poseai.session_manager")

# Per-user engine registry.  Key = user_id string from Flask session.
_engines_by_user: dict[str, "WebWorkoutEngine"] = {}  # type: ignore[name-defined]

# Shared default engine for unauthenticated / desktop callers.
_default_engine: Optional["WebWorkoutEngine"] = None  # type: ignore[name-defined]


def get_or_create_engine(user_id: Optional[str] = None) -> "WebWorkoutEngine":  # type: ignore[name-defined]
    """Return the WebWorkoutEngine for *user_id*.

    Authenticated web users get an isolated engine keyed by their
    session user_id so one user's workout can never overwrite
    another user's frames.  Unauthenticated callers (legacy
    desktop main.py) share the default engine.

    Engines are created lazily on first use, so the model
    initialisation cost is only paid once per user per server
    restart.
    """
    # Import here (not at module top) to avoid a circular import chain:
    # app.py -> session_manager (top-level import) -> web_workout_engine
    # -> exercise_router -> workouts/* is fine.  The only risk is if
    # web_workout_engine imported app.py, which it does not.
    from core.web_workout_engine import WebWorkoutEngine  # noqa: PLC0415

    if user_id:
        engine = _engines_by_user.get(user_id)
        if engine is None:
            logger.info("[SESSION] Creating new engine for user %s", user_id)
            engine = WebWorkoutEngine(debug=True)
            _engines_by_user[user_id] = engine
        return engine

    global _default_engine
    if _default_engine is None:
        logger.info("[SESSION] Creating default (anonymous) engine")
        _default_engine = WebWorkoutEngine(debug=True)
    return _default_engine


def get_engine_for_user(user_id: str) -> Optional["WebWorkoutEngine"]:  # type: ignore[name-defined]
    """Return the existing engine for *user_id* without creating one.

    Returns None if no engine has been initialised for this user yet.
    Used by finish_workout to call engine.finish() only when an engine
    actually exists for the session.
    """
    return _engines_by_user.get(user_id)
