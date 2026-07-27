"""
PoseAI - AI Fitness Trainer
app.py

Flask API Bridge
-------------------------------------------------------------------------
Responsibilities:
    - Act as the communication bridge between the Python workout engine
      (main.py) and the web dashboard (dashboard/js/api.js)
    - Maintain a single in-memory dashboard state dictionary
    - Expose REST endpoints for reading dashboard/workout data and for
      receiving state updates from main.py

This file NEVER:
    - Talks to MediaPipe or OpenCV
    - Performs pose detection
    - Calculates reps/sets/angles itself

Architecture:
    main.py (Workout Engine) -> app.py (Flask API) -> api.js -> dashboard.js -> index.html
-------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from flask import Flask, jsonify, request, Response, send_from_directory

from core.web_workout_engine import WebWorkoutEngine

try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover - defensive fallback for minimal installs
    CORS = None

# ==============================================================================
# APP / LOGGING CONFIGURATION
# ==============================================================================

app = Flask(__name__, static_folder="dashboard", static_url_path="")
if CORS is not None:
    CORS(app, resources={r"/api/*": {"origins": "*"}})

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("poseai.app")

HOST: str = "0.0.0.0"
PORT: int = 5000

_engine = None


def get_or_create_workout_engine() -> WebWorkoutEngine:
    global _engine
    if _engine is None:
        _engine = WebWorkoutEngine(debug=True)
    return _engine


def process_workout_frame(encoded_frame: str | None, exercise: str | None = None) -> dict[str, Any]:
    engine = get_or_create_workout_engine()
    payload = engine.process_frame(encoded_frame=encoded_frame, exercise=exercise)
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

# Single source of truth for everything the dashboard displays.
# main.py updates this via POST /api/update; every GET endpoint below
# reads from (a slice of) this dictionary.
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
# ROUTES
# ==============================================================================

@app.route("/", methods=["GET"])
def root() -> tuple[Response, int] | Response:
    """
    GET /

    Serves the dashboard HTML when requested from a browser and returns
    a JSON health payload for API-style requests.
    """
    accepts_html = "text/html" in request.headers.get("Accept", "")
    if accepts_html:
        try:
            return send_from_directory(app.static_folder, "index.html")
        except FileNotFoundError:
            return _error_response("Dashboard index not found.", 404)

    try:
        return _success_response(
            data={"service": "PoseAI Flask API", "status": "running"},
            message="PoseAI backend is online.",
        )
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Health check failed: {error}", 500)


@app.route("/dashboard", methods=["GET"])
def dashboard_index() -> tuple[Response, int] | Response:
    """Alias route for serving the dashboard UI from localhost."""
    try:
        return send_from_directory(app.static_folder, "index.html")
    except FileNotFoundError:
        return _error_response("Dashboard index not found.", 404)


@app.route("/api/status", methods=["GET"])
def get_status() -> tuple[Response, int]:
    """
    GET /api/status

    Returns the full current dashboard state as-is. This is the primary
    endpoint polled by api.js for live dashboard updates.
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


@app.route("/api/statistics", methods=["GET"])
def get_statistics() -> tuple[Response, int]:
    """
    GET /api/statistics

    Returns today's performance statistics (total reps, workout time,
    calories, xp, exercises completed).
    """
    try:
        logger.info("Request received: GET /api/statistics")
        return _success_response(data=dashboard_state["statistics"])
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to retrieve statistics: {error}", 500)


@app.route("/api/stats", methods=["GET"])
def get_stats_alias() -> tuple[Response, int]:
    """Backward-compatible alias for the statistics endpoint."""
    return get_statistics()


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


@app.route("/api/streak", methods=["GET"])
def get_streak() -> tuple[Response, int]:
    """
    GET /api/streak

    Returns the current streak and today's goal completion percentage.
    """
    try:
        logger.info("Request received: GET /api/streak")
        streak_data = {
            "streak": dashboard_state["streak"],
            "goal": dashboard_state["goal"],
        }
        return _success_response(data=streak_data)
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to retrieve streak data: {error}", 500)


@app.route("/api/achievements", methods=["GET"])
def get_achievements() -> tuple[Response, int]:
    """
    GET /api/achievements

    Returns the list of achievements. Achievement data is expected to
    be pushed into dashboard_state by main.py via POST /api/update
    under a future "achievements" field; until then, an empty list is
    returned rather than fabricated data.
    """
    try:
        logger.info("Request received: GET /api/achievements")
        achievements = dashboard_state.get("achievements", [])
        return _success_response(data=achievements)
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to retrieve achievements: {error}", 500)


@app.route("/api/workout/start", methods=["POST"])
def start_workout_session() -> tuple[Response, int]:
    """Start or switch the active workout session from the dashboard."""
    try:
        payload = request.get_json(silent=True) or {}
        exercise_key = payload.get("exercise")
        engine = get_or_create_workout_engine()
        if exercise_key:
            if hasattr(engine, "set_exercise"):
                engine.set_exercise(exercise_key)
            elif hasattr(engine, "start"):
                engine.start(exercise_key)
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


@app.route("/api/workout/finish", methods=["POST"])
def finish_workout_session() -> tuple[Response, int]:
    try:
        engine = get_or_create_workout_engine()
        status = _coerce_engine_status(engine)
        if hasattr(engine, "finish"):
            status = engine.finish()
        dashboard_state.update({"cameraStatus": status.get("cameraStatus", dashboard_state.get("cameraStatus")), "feedback": status.get("feedback", dashboard_state.get("feedback"))})
        return _success_response(data=status)
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to finish workout session: {error}", 500)


@app.route("/api/workout/frame", methods=["POST"])
def workout_frame_update() -> tuple[Response, int]:
    try:
        payload = request.get_json(silent=True) or {}
        encoded_frame = payload.get("image")
        exercise = payload.get("exercise")
        workout_payload = process_workout_frame(encoded_frame=encoded_frame, exercise=exercise)
        return _success_response(data={**workout_payload, "cameraStatus": workout_payload.get("cameraStatus", "tracking")})
    except Exception as error:  # noqa: BLE001
        return _error_response(f"Failed to process workout frame: {error}", 500)


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
    """Handles unexpected internal server errors without crashing the app."""
    return _error_response("An unexpected internal server error occurred.", 500)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    logger.info("Starting PoseAI Flask API on %s:%s ...", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=False, threaded=True)