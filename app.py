"""
PoseAI - AI Fitness Trainer
app.py

Flask API Bridge + Web Server
-------------------------------------------------------------------------
Responsibilities:
    - Act as the communication bridge between the Python workout engine
      (main.py) and the web dashboard (frontend/html/* + frontend/js/*)
    - Maintain a single in-memory dashboard state dictionary (the legacy
      desktop engine bridge from main.py)
    - Expose REST endpoints for reading dashboard/workout data and for
      receiving state updates from main.py
    - Serve the authenticated web frontend (frontend/) and register the
      authentication (auth.py) and user-data (dashboard_api.py) blueprints

This file NEVER:
    - Talks to MediaPipe or OpenCV
    - Performs pose detection
    - Calculates reps/sets/angles itself

Architecture:
    main.py (Workout Engine) -> app.py (Flask API) -> frontend/js/api.js
                               -> frontend/html/index.html
    Auth (auth.py)            -> MongoDB users
    Dashboard data            -> dashboard_api.py -> database.workouts
-------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, Response, redirect, send_from_directory, session
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from auth import auth_bp, limiter
from config import Config
from core.web_workout_engine import WebWorkoutEngine
from core.session_manager import get_or_create_engine as _sm_get_engine
from dashboard_api import api_bp
from market import market_bp
from nutrition import nutrition_bp

try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover - defensive fallback for minimal installs
    CORS = None

# ==============================================================================
# APP / LOGGING CONFIGURATION
# ==============================================================================

app = Flask(__name__, static_folder=None)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# Ensure reverse proxies like Render pass real client protocol and host
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_port=1,
    x_prefix=1,
)

# Explicitly ensure session cookie settings
app.config["SESSION_COOKIE_NAME"] = Config.SESSION_COOKIE_NAME
app.config["SESSION_COOKIE_HTTPONLY"] = Config.SESSION_COOKIE_HTTPONLY
app.config["SESSION_COOKIE_SECURE"] = Config.SESSION_COOKIE_SECURE
app.config["SESSION_COOKIE_SAMESITE"] = Config.SESSION_COOKIE_SAMESITE
app.config["SESSION_COOKIE_PATH"] = Config.SESSION_COOKIE_PATH
app.config["PERMANENT_SESSION_LIFETIME"] = Config.PERMANENT_SESSION_LIFETIME

CORS_ORIGINS = Config.CORS_ORIGINS
if CORS is not None:
    if CORS_ORIGINS and CORS_ORIGINS != "*":
        origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
        CORS(app, resources={r"/api/*": {"origins": origins}, r"/auth/*": {"origins": origins}}, supports_credentials=True)
    elif not Config.IS_PRODUCTION:
        CORS(app, resources={r"/api/*": {"origins": r".*"}, r"/auth/*": {"origins": r".*"}}, supports_credentials=True)

if limiter is not None:
    try:
        limiter.init_app(app)
    except Exception as _lim_err:  # pragma: no cover
        logging.getLogger("poseai.app").warning("Could not attach limiter to app: %s", _lim_err)

@app.after_request
def set_security_headers(response: Response) -> Response:
    """Security hardening headers (Helmet equivalent)."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if Config.IS_PRODUCTION or request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.register_blueprint(auth_bp)
app.register_blueprint(api_bp)
app.register_blueprint(market_bp)
app.register_blueprint(nutrition_bp)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("poseai.app")

HOST: str = "0.0.0.0"
PORT: int = Config.PORT

# Engine registry is now managed in core/session_manager.py to avoid a
# circular import when dashboard_api.py also needs engine access.
# These aliases keep existing call-sites inside this file working unchanged.

# ==============================================================================
# FRONTEND
# ==============================================================================

_FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
_FRONTEND_HTML_DIR = _FRONTEND_DIR / "html"
_FRONTEND_JS_DIR = _FRONTEND_DIR / "js"
_FRONTEND_CSS_DIR = _FRONTEND_DIR / "css"
_FRONTEND_IMAGES_DIR = _FRONTEND_DIR / "images"

# Page path -> html file (all authenticated except the auth pages).
PAGE_ROUTES: dict[str, str] = {
    "workout": "workout.html",
    "analysis": "analysis.html",
    "progress": "progress.html",
    "profile": "profile.html",
    "exercises": "exercises.html",
    "achievements": "achievements.html",
    "game": "game.html",
    "nutrition": "nutrition.html",
    "fitness-market": "fitness_market.html",
    "market": "fitness_market.html",
    "cart": "cart.html",
    "checkout": "checkout.html",
    "orders": "orders.html",
    "favorites": "favorites.html",
    "products": "products.html",
}


def _is_authenticated() -> bool:
    return session.get("user_id") is not None


def _current_user_key() -> str:
    """Server-side user id for logging (never trusts client input)."""
    return str(session.get("user_id") or "anonymous")


def _require_login():
    """Redirect HTML requests to /login when there is no authenticated session."""
    if not _is_authenticated():
        return redirect("/login")
    return None


def _serve_page(filename: str) -> Response:
    return send_from_directory(_FRONTEND_HTML_DIR, filename)


# ==============================================================================
# WORKOUT ENGINE BRIDGE
# ==============================================================================

def get_or_create_workout_engine() -> WebWorkoutEngine:
    """
    Return the WebWorkoutEngine for the current request context.

    Delegates to core.session_manager so that dashboard_api.py can also
    call the same registry without creating a circular import.
    """
    user_id = session.get("user_id")
    return _sm_get_engine(user_id)


def process_workout_frame(encoded_frame: str | None, exercise: str | None = None) -> dict[str, Any]:
    """Decode one browser frame and run it through the user's workout engine.

    Single integration point between the live-camera API and
    core.web_workout_engine.WebWorkoutEngine ("one engine, two input
    sources"). All pose/angle/rep/stage/feedback math lives in the shared
    ExerciseRouter + workouts/* — this function only routes and mirrors.
    """
    from core.exercise_router import normalize_exercise_key

    engine = get_or_create_workout_engine()
    canonical_exercise = normalize_exercise_key(exercise) if exercise else None
    if exercise and canonical_exercise is None:
        logger.warning("[WORKOUT] Unknown exercise '%s'; keeping current selection", exercise)
    payload = engine.process_frame(
        encoded_frame=encoded_frame,
        exercise=canonical_exercise if canonical_exercise is not None else None,
    )
    dashboard_state.update(
        {
            "exercise": payload.get("exercise", dashboard_state.get("exercise")),
            "currentRep": payload.get("currentRep", dashboard_state.get("currentRep")),
            "goalRep": payload.get("goalRep", dashboard_state.get("goalRep")),
            "currentSet": payload.get("currentSet", dashboard_state.get("currentSet")),
            "goalSet": payload.get("goalSet", dashboard_state.get("goalSet")),
            "stage": payload.get("stage", dashboard_state.get("stage")),
            "angle": payload.get("angle", dashboard_state.get("angle")),
            "calories": payload.get("calories", dashboard_state.get("calories")),
            "workoutTime": payload.get("workoutTime", dashboard_state.get("workoutTime")),
            "feedback": payload.get("feedback", dashboard_state.get("feedback")),
            "xp": payload.get("xp", dashboard_state.get("xp")),
            "streak": payload.get("streak", dashboard_state.get("streak")),
            "goal": payload.get("goal", dashboard_state.get("goal")),
            "statistics": payload.get("statistics", dashboard_state.get("statistics")),
            "coach": payload.get("coach", dashboard_state.get("coach")),
            "summary": payload.get("summary", dashboard_state.get("summary")),
            "cameraStatus": payload.get("cameraStatus", dashboard_state.get("cameraStatus")),
        }
    )
    return payload


def _coerce_engine_status(engine: Any) -> dict[str, Any]:
    if hasattr(engine, "get_status"):
        status = engine.get_status()
        if isinstance(status, dict):
            return status
    if hasattr(engine, "status") and isinstance(engine.status, dict):
        return engine.status
    return {}


# ==============================================================================
# GLOBAL DASHBOARD STATE
# ==============================================================================

# Single source of truth for everything the legacy desktop dashboard
# displays. main.py updates this via POST /api/update; every GET endpoint
# below reads from (a slice of) this dictionary.
dashboard_state: dict[str, Any] = {
    "exercise": "No Exercise Selected",
    "currentRep": 0,
    "goalRep": 15,
    "currentSet": 0,
    "goalSet": 3,
    "stage": "Waiting...",
    "angle": None,
    "calories": 0.0,
    "workoutTime": "00:00",
    "feedback": "Waiting for Camera...",
    "xp": 0,
    "streak": 0,
    "goal": 0,
    "statistics": {
        "totalReps": 0,
        "workoutTime": "00:00",
        "calories": 0.0,
        "xp": 0,
        "exercisesCompleted": 0,
    },
    "coach": {
        "message": "",
        "type": "info",
    },
    "summary": {
        "exercise": "--",
        "sets": 0,
        "reps": 0,
        "workoutTime": "00:00",
        "calories": 0.0,
        "xp": 0,
        "streak": 0,
    },
    "cameraStatus": "offline",
}

# Fields that POST /api/update is allowed to modify. Anything outside
# this set is ignored rather than trusted blindly.
ALLOWED_UPDATE_FIELDS: set[str] = {
    "exercise",
    "currentRep",
    "goalRep",
    "currentSet",
    "goalSet",
    "stage",
    "angle",
    "calories",
    "workoutTime",
    "feedback",
    "xp",
    "streak",
    "goal",
    "statistics",
    "coach",
    "summary",
    "cameraStatus",
}


# ==============================================================================
# HELPERS
# ==============================================================================

def _success_response(data: Any = None, message: str = "OK", status_code: int = 200) -> tuple[Response, int]:
    """Builds a standardized success JSON response."""
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code


def _error_response(message: str, status_code: int = 400) -> tuple[Response, int]:
    """Builds a standardized error JSON response."""
    logger.error("Request failed: %s", message)
    return jsonify({"success": False, "error": message}), status_code


def _validate_update_payload(payload: Any) -> tuple[bool, str]:
    """
    Validates the incoming JSON payload for POST /api/update.

    Ensures the payload is a non-empty dictionary and that at least one
    key is a recognized dashboard field. Rejects malformed payloads
    without ever crashing the server.

    Returns:
        (is_valid, error_message)
    """
    if payload is None:
        return False, "Request body must be valid JSON."

    if not isinstance(payload, dict):
        return False, "Request body must be a JSON object."

    if len(payload) == 0:
        return False, "Request body cannot be empty."

    recognized_keys = [key for key in payload.keys() if key in ALLOWED_UPDATE_FIELDS]
    if not recognized_keys:
        return False, f"No recognized fields in payload. Allowed fields: {sorted(ALLOWED_UPDATE_FIELDS)}"

    return True, ""


def _apply_update(payload: dict[str, Any]) -> list[str]:
    """
    Applies validated fields from the payload onto the global dashboard
    state. Nested dict fields (statistics, coach, summary) are merged
    rather than replaced outright, so partial updates don't wipe
    sibling keys.

    Returns:
        List of field names that were actually updated.
    """
    updated_fields: list[str] = []

    for key, value in payload.items():
        if key not in ALLOWED_UPDATE_FIELDS:
            continue

        current_value = dashboard_state.get(key)
        if isinstance(current_value, dict) and isinstance(value, dict):
            current_value.update(value)
            dashboard_state[key] = current_value
        else:
            dashboard_state[key] = value

        updated_fields.append(key)

    return updated_fields


# ==============================================================================
# ROUTES — PAGES
# ==============================================================================

@app.route("/", methods=["GET"])
def root() -> tuple[Response, int] | Response:
    """
    GET /

    Serves the (authenticated) dashboard HTML when requested from a
    browser and returns a JSON health payload for API-style requests.
    """
    accepts_html = "text/html" in request.headers.get("Accept", "")
    if accepts_html:
        guard = _require_login()
        if guard is not None:
            return guard
        try:
            return _serve_page("index.html")
        except FileNotFoundError:
            return _error_response("Frontend index not found.", 404)

    try:
        return _success_response(
            data={"service": "PoseAI Flask API", "status": "running"},
            message="PoseAI backend is online.",
        )
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Health check failed: {error}", 500)


@app.route("/dashboard", methods=["GET"])
def dashboard_index() -> tuple[Response, int] | Response:
    """Alias route for serving the dashboard UI to authenticated users."""
    guard = _require_login()
    if guard is not None:
        return guard
    try:
        return _serve_page("index.html")
    except FileNotFoundError:
        return _error_response("Frontend index not found.", 404)


@app.route("/login", methods=["GET"])
def login_page() -> Response:
    """Serve the login page (public)."""
    return _serve_page("login.html")


@app.route("/signup", methods=["GET"])
def signup_page() -> Response:
    """Serve the signup page (public)."""
    return _serve_page("signup.html")


@app.route("/<page>", methods=["GET"])
def frontend_page(page: str) -> Response:
    """Serve an authenticated frontend page by name (e.g. /workout)."""
    filename = PAGE_ROUTES.get(page)
    if filename is None:
        return _error_response("The requested endpoint does not exist.", 404)
    guard = _require_login()
    if guard is not None:
        return guard
    return _serve_page(filename)


# ==============================================================================
# ROUTES — FRONTEND STATIC ASSETS
# ==============================================================================

@app.route("/js/<path:filename>", methods=["GET"])
def frontend_js(filename: str) -> Response:
    return send_from_directory(_FRONTEND_JS_DIR, filename)


@app.route("/css/<path:filename>", methods=["GET"])
def frontend_css(filename: str) -> Response:
    return send_from_directory(_FRONTEND_CSS_DIR, filename)


@app.route("/images/<path:filename>", methods=["GET"])
def frontend_images(filename: str) -> Response:
    return send_from_directory(_FRONTEND_IMAGES_DIR, filename)


@app.route("/market/images/<path:filename>", methods=["GET"])
@app.route("/fitness_market_product_image/<path:filename>", methods=["GET"])
def market_product_images(filename: str) -> Response:
    return send_from_directory(_FRONTEND_IMAGES_DIR / "market_products", filename)


# ==============================================================================
# ROUTES — HEALTH & ENGINE BRIDGE / LIVE WORKOUT DATA
# ==============================================================================

@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def api_health() -> tuple[Response, int]:
    """
    GET /api/health

    Production health-check endpoint for Render / monitoring.
    Verifies database connectivity safely without exposing secrets.
    """
    db_status = "disconnected"
    db_mode = "unknown"
    try:
        from database import mongo as mongo_db
        db = mongo_db.get_db()
        if db is not None:
            db.command("ping")
            db_status = "connected"
            db_mode = "mock" if mongo_db.is_mock() else "live_mongodb"
    except Exception as exc:
        db_status = "error"
        db_mode = str(exc)[:120]

    return jsonify({
        "success": True,
        "status": "healthy",
        "database": db_status,
        "database_mode": db_mode,
        "environment": Config.ENVIRONMENT,
    }), 200


@app.route("/api/status", methods=["GET"])
def get_status() -> tuple[Response, int]:
    """
    GET /api/status

    Returns the full current dashboard state as-is. This is the primary
    endpoint polled by the legacy dashboard for live updates.
    """
    try:
        logger.info("Request received: GET /api/status")
        return _success_response(data=dashboard_state)
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to retrieve status: {error}", 500)


@app.route("/api/workout", methods=["GET"])
def get_workout() -> tuple[Response, int]:
    """
    GET /api/workout

    Returns only the fields relevant to the live workout panel
    (exercise, reps, sets, stage, angle, calories, time, feedback).
    """
    try:
        logger.info("Request received: GET /api/workout")
        workout_data = {
            "exercise": dashboard_state.get("exercise"),
            "currentRep": dashboard_state.get("currentRep"),
            "goalRep": dashboard_state.get("goalRep"),
            "currentSet": dashboard_state.get("currentSet"),
            "goalSet": dashboard_state.get("goalSet"),
            "stage": dashboard_state.get("stage"),
            "angle": dashboard_state.get("angle"),
            "calories": dashboard_state.get("calories"),
            "workoutTime": dashboard_state.get("workoutTime"),
            "feedback": dashboard_state.get("feedback"),
            "cameraStatus": dashboard_state.get("cameraStatus"),
            "xp": dashboard_state.get("xp"),
            "streak": dashboard_state.get("streak"),
            "goal": dashboard_state.get("goal"),
            "statistics": dashboard_state.get("statistics", {}),
            "coach": dashboard_state.get("coach", {}),
            "summary": dashboard_state.get("summary", {}),
        }
        return _success_response(data=workout_data)
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to retrieve workout data: {error}", 500)


@app.route("/api/session", methods=["GET"])
def get_session() -> tuple[Response, int]:
    """
    GET /api/session

    Returns the session summary (final results of the last completed
    workout session).
    """
    try:
        logger.info("Request received: GET /api/session")
        return _success_response(data=dashboard_state["summary"])
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to retrieve session summary: {error}", 500)


@app.route("/api/coach", methods=["GET"])
def get_coach() -> tuple[Response, int]:
    """
    GET /api/coach

    Returns the latest AI coach feedback message and its semantic type
    (success, warning, error, info).
    """
    try:
        logger.info("Request received: GET /api/coach")
        return _success_response(data=dashboard_state["coach"])
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to retrieve coach feedback: {error}", 500)


@app.route("/api/camera", methods=["GET"])
def get_camera_status() -> tuple[Response, int]:
    """Convenience endpoint exposing the camera status to the frontend."""
    try:
        return _success_response(data={"cameraStatus": dashboard_state.get("cameraStatus", "offline")})
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to retrieve camera status: {error}", 500)


@app.route("/api/connect", methods=["GET"])
def get_connection_status() -> tuple[Response, int]:
    """Convenience endpoint exposing the connection state."""
    try:
        return _success_response(data={"connected": dashboard_state.get("cameraStatus") == "online"})
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to retrieve connection status: {error}", 500)


@app.route("/api/workout/start", methods=["POST"])
def start_workout_session() -> tuple[Response, int]:
    """Start or switch the active workout session from the dashboard."""
    try:
        from core.exercise_router import normalize_exercise_key

        payload = request.get_json(silent=True) or {}
        exercise_key = payload.get("exercise") or request.args.get("exercise")
        canonical = normalize_exercise_key(exercise_key) if exercise_key else None
        if exercise_key and canonical is None:
            return _error_response("Unknown exercise '{0}'. Use a key like '1' or a slug like 'bicep_curl'.".format(exercise_key), 400)
        engine = get_or_create_workout_engine()
        if canonical:
            if hasattr(engine, "set_exercise"):
                engine.set_exercise(canonical)
            elif hasattr(engine, "start"):
                engine.start(canonical)
        else:
            if hasattr(engine, "start"):
                engine.start()
        status = _coerce_engine_status(engine)
        dashboard_state.update({
            "exercise": status.get("exercise", dashboard_state.get("exercise")),
            "currentRep": status.get("currentRep", dashboard_state.get("currentRep")),
            "goalRep": status.get("goalRep", dashboard_state.get("goalRep")),
            "currentSet": status.get("currentSet", dashboard_state.get("currentSet")),
            "goalSet": status.get("goalSet", dashboard_state.get("goalSet")),
            "stage": status.get("stage", dashboard_state.get("stage")),
            "angle": status.get("angle", dashboard_state.get("angle")),
            "calories": status.get("calories", dashboard_state.get("calories")),
            "workoutTime": status.get("workoutTime", dashboard_state.get("workoutTime")),
            "feedback": status.get("feedback", dashboard_state.get("feedback")),
            "xp": status.get("xp", dashboard_state.get("xp")),
            "streak": status.get("streak", dashboard_state.get("streak")),
            "goal": status.get("goal", dashboard_state.get("goal")),
            "statistics": status.get("statistics", dashboard_state.get("statistics")),
            "coach": status.get("coach", dashboard_state.get("coach")),
            "summary": status.get("summary", dashboard_state.get("summary")),
            "cameraStatus": status.get("cameraStatus", dashboard_state.get("cameraStatus")),
        })
        logger.info("[WORKOUT] Session started")
        return _success_response(data={"exercise": status.get("exercise"), "cameraStatus": status.get("cameraStatus")})
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to start workout session: {error}", 500)


@app.route("/api/workout/pause", methods=["POST"])
def pause_workout_session() -> tuple[Response, int]:
    try:
        engine = get_or_create_workout_engine()
        status = _coerce_engine_status(engine)
        if hasattr(engine, "pause"):
            status = engine.pause()
        dashboard_state.update({"cameraStatus": status.get("cameraStatus", dashboard_state.get("cameraStatus")), "feedback": status.get("feedback", dashboard_state.get("feedback"))})
        return _success_response(data=status)
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to pause workout session: {error}", 500)


@app.route("/api/workout/resume", methods=["POST"])
def resume_workout_session() -> tuple[Response, int]:
    try:
        engine = get_or_create_workout_engine()
        status = _coerce_engine_status(engine)
        if hasattr(engine, "resume"):
            status = engine.resume()
        dashboard_state.update({"cameraStatus": status.get("cameraStatus", dashboard_state.get("cameraStatus")), "feedback": status.get("feedback", dashboard_state.get("feedback"))})
        return _success_response(data=status)
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to resume workout session: {error}", 500)


@app.route("/api/workout/frame", methods=["POST"])
def workout_frame_update() -> tuple[Response, int]:
    """POST /api/workout/frame — live browser-camera frame processing.

    Expected JSON: {"image": "data:image/jpeg;base64,...", "exercise": "1"}.
    The image flows: browser canvas -> base64 -> WebWorkoutEngine ->
    OpenCV/MediaPipe -> ExerciseRouter -> workouts/* -> live metrics JSON.
    Validation failures return 4xx with a structured error (never fake
    metrics); decode/detection misses return 200 with pose_detected=false.
    """
    user_key = _current_user_key()
    try:
        payload = request.get_json(silent=True)
        if payload is None:
            return _error_response("Request body must be JSON with 'image' and 'exercise'.", 400)
        if not isinstance(payload, dict):
            return _error_response("Request body must be a JSON object.", 400)
        encoded_frame = payload.get("image")
        exercise = payload.get("exercise")
        if not isinstance(encoded_frame, str) or not encoded_frame.strip():
            return _error_response("Field 'image' is required and must be a non-empty base64 string.", 400)
        if len(encoded_frame) > 8_000_000:
            return _error_response("Frame payload too large; reduce capture resolution/quality.", 413)
        if not isinstance(exercise, str) or not exercise.strip():
            return _error_response("Field 'exercise' is required (e.g. '1' or 'bicep_curl').", 400)
        logger.info(
            "[WORKOUT] Frame request | User: %s | Exercise: %s | Image bytes: %s",
            _current_user_key(), exercise, len(encoded_frame),
        )
        workout_payload = process_workout_frame(encoded_frame=encoded_frame, exercise=exercise)
        logger.info(
            "[WORKOUT] Frame result | User: %s | Exercise: %s | Rep: %s | Angle: %s | Stage: %s | Pose: %s | Calories: %s",
            user_key, workout_payload.get("exercise"),
            workout_payload.get("currentRep"),
            workout_payload.get("angle"),
            workout_payload.get("stage"),
            workout_payload.get("pose_detected"),
            workout_payload.get("calories"),
        )
        return _success_response(data={**workout_payload, "cameraStatus": workout_payload.get("cameraStatus", "tracking")})
    except Exception as error:  # noqa: BLE001
        logger.exception("[WORKOUT] Frame processing failed | User: %s", user_key)
        return _error_response(f"Frame processing failed: {error}", 500)


@app.route("/api/workout/session", methods=["GET"])
def get_workout_session() -> tuple[Response, int]:
    """
    GET /api/workout/session

    Reports whether the current user has an active (unfinished) workout
    session left over in the engine. The workout page uses this on load to
    offer a "resume active session" instead of silently starting fresh.
    """
    try:
        if not _is_authenticated():
            return _success_response(data={"active": False})
        engine = get_or_create_workout_engine()
        status = _coerce_engine_status(engine)
        session_status = status.get("sessionStatus", "idle")
        active = session_status in ("active", "paused")
        return _success_response(
            data={
                "active": active,
                "exercise": status.get("exercise") if active else None,
                "exerciseKey": getattr(engine, "current_key", None) if active else None,
                "currentRep": status.get("currentRep") if active else 0,
                "goalRep": status.get("goalRep") if active else 0,
                "currentSet": status.get("currentSet") if active else 0,
                "goalSet": status.get("goalSet") if active else 0,
                "workoutTime": status.get("workoutTime") if active else None,
                "paused": session_status == "paused",
            }
        )
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to read workout session: {error}", 500)


@app.route("/api/workout/continue", methods=["POST"])
def continue_to_next_set() -> tuple[Response, int]:
    """
    POST /api/workout/continue

    Called when the user clicks "Continue to Next Set" after completing a set.
    This tells the engine to advance to the next set and reset the rep counter.
    """
    try:
        if not _is_authenticated():
            return _error_response("Authentication required.", 401)
        engine = get_or_create_workout_engine()
        # Call the engine's method to advance to next set
        if hasattr(engine, "advance_to_next_set"):
            engine.advance_to_next_set()
        elif hasattr(engine, "_advance_to_next_set"):
            engine._advance_to_next_set()
        # Get the updated status to return
        status = _coerce_engine_status(engine)
        return _success_response(data=status)
    except Exception as error:  # noqa: BLE001
        logger.exception("[WORKOUT] Continue to next set failed")
        return _error_response(f"Failed to continue: {error}", 500)


@app.route("/api/update", methods=["POST"])
def update_dashboard() -> tuple[Response, int]:
    """
    POST /api/update

    Receives updated workout data from main.py (the workout engine) and
    merges it into the global dashboard state after validation. Only
    recognized fields are applied; nested objects (statistics, coach,
    summary) are merged rather than overwritten wholesale.
    """
    try:
        logger.info("Request received: POST /api/update")

        payload = request.get_json(silent=True)
        is_valid, validation_message = _validate_update_payload(payload)

        if not is_valid:
            return _error_response(validation_message, 400)

        updated_fields = _apply_update(payload)
        logger.info("Workout updated. Fields changed: %s", updated_fields)

        return _success_response(
            data={"updatedFields": updated_fields, "timestamp": datetime.utcnow().isoformat()},
            message="Dashboard state updated successfully.",
        )
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to update dashboard state: {error}", 500)


# ==============================================================================
# ERROR HANDLERS
# ==============================================================================

@app.errorhandler(404)
def handle_not_found(error: Any) -> tuple[Response, int]:
    """Handles requests to undefined routes."""
    return _error_response("The requested endpoint does not exist.", 404)


@app.errorhandler(405)
def handle_method_not_allowed(error: Any) -> tuple[Response, int]:
    """Handles requests using an unsupported HTTP method."""
    return _error_response("This HTTP method is not allowed for this endpoint.", 405)


@app.errorhandler(500)
def handle_internal_server_error(error: Any) -> tuple[Response, int]:
    """Handles unexpected internal server errors without crashing the app or leaking traces."""
    logger.exception("Internal server error: %s", error)
    if Config.IS_PRODUCTION:
        return _error_response("An unexpected internal server error occurred.", 500)
    return _error_response(f"Internal server error: {error}", 500)


@app.errorhandler(Exception)
def handle_unhandled_exception(error: Exception) -> tuple[Response, int]:
    """Catches unhandled exceptions and prevents information leakage in production."""
    if isinstance(error, HTTPException):
        return _error_response(error.description, error.code)
    logger.exception("Unhandled application exception: %s", error)
    if Config.IS_PRODUCTION:
        return _error_response("An unexpected internal server error occurred.", 500)
    return _error_response(f"Internal error: {error}", 500)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    logger.info("Starting PoseAI Flask API on %s:%s ...", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=False, threaded=True)