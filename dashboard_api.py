"""
PoseAI — Dashboard / User Data API Blueprint

Implements every endpoint the authenticated frontend pages (index,
workout, analysis, progress, achievements, exercises, profile) depend
on. Backed by:
    - core/exercise_data.py   (static exercise catalog)
    - database.workouts       (MongoDB workout sessions / stats / achievements)
    - database.mongo          (MongoDB users)
    - auth                    (password hashing / breach checks)

All endpoints require an authenticated session (login_required). The
engine-bridge endpoints (/api/status, /api/update, /api/workout/start,
/api/workout/frame, ...) intentionally remain in app.py, unauthenticated,
so the desktop OpenCV/MediaPipe engine (main.py) can keep pushing data.

Response convention: every endpoint returns JSON
    {"success": bool, "message": str, "data": <payload>}
unless noted otherwise (e.g. /api/data/export returns an attachment).
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

from bson import ObjectId
from flask import Blueprint, Response, jsonify, request, session
from pymongo import DESCENDING

from auth import (
    get_min_password_length,
    hash_password,
    is_password_breached,
    login_required,
    verify_password,
)
from core.exercise_data import EXERCISE_DATA, get_exercise_info
from core.session_manager import get_engine_for_user
from database import mongo as mongo_db
from database import workouts as workouts_db
from models import ACHIEVEMENT_DEFINITIONS, ACHIEVEMENT_MAP

api_bp = Blueprint("dashboard_api", __name__)

# Tracks the last time each user finished a workout so a double-POST of the
# same /api/workout/finish (browser retry / double-click) cannot insert the
# same session twice. Keyed by user_id -> (utc_ts, previous_response_data).
_last_finish_by_user: dict[str, tuple[float, dict]] = {}
FINISH_IDEMPOTENCY_WINDOW_SECONDS = 5.0


def _err(message: str, status_code: int = 400) -> tuple[Response, int]:
    return jsonify(success=False, error=message), status_code


def _ok(data: Any = None, message: str = "OK", status_code: int = 200, **kwargs: Any) -> tuple[Response, int]:
    payload: dict[str, Any] = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return jsonify(payload), status_code


# ==============================================================================
#  EXERCISES
# ==============================================================================

@api_bp.route("/api/exercises", methods=["GET"])
@login_required
def list_exercises():
    """Return the static exercise catalog for the workout / exercises pages."""
    exercises = []
    for key, info in EXERCISE_DATA.items():
        exercises.append({
            "id": key,
            "name": info["name"],
            "difficulty": info.get("difficulty", "Intermediate"),
            "goal": int(info.get("goal", 15) or 15),
            "sets": int(info.get("sets", 3) or 3),
            "description": info["instructions"][0] if info.get("instructions") else "",
            "muscles": [m.strip() for m in info["target"].split("/") if m.strip()],
        })
    return _ok(data=exercises, message="Exercise catalog loaded.")


# ==============================================================================
#  STREAK / STATISTICS (dashboard hero cards)
# ==============================================================================

@api_bp.route("/api/streak", methods=["GET"])
@login_required
def get_streak():
    """Current + longest streak computed from persisted sessions."""
    user_id = session["user_id"]
    try:
        ctx = workouts_db.streak_context(user_id)
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)
    return _ok(data=ctx, message="Streak loaded.")


@api_bp.route("/api/statistics", methods=["GET"])
@login_required
def get_statistics():
    """Lifetime aggregates driving the dashboard hero cards.

    Includes both the new web-dashboard field names (totalWorkouts,
    totalRepsAllTime, ...) and the legacy dashboard_state keys so older
    widgets keep working.
    """
    user_id = session["user_id"]
    try:
        stats = workouts_db.get_or_create_user_stats(user_id)
        current, longest, _, _ = workouts_db.calculate_streak_for_user(user_id)
        avg_form = workouts_db.average_form_score(user_id)
        today = workouts_db.today_performance(user_id)
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)

    data = {
        "totalWorkouts": int(stats.get("total_workouts", 0)),
        "longestStreak": max(longest, int(stats.get("longest_streak", 0))),
        "averageFormScore": round(avg_form, 1),
        "totalRepsAllTime": int(stats.get("total_reps", 0)),
        "totalCaloriesAllTime": round(float(stats.get("total_calories", 0.0)), 1),
        # legacy keys for compatibility
        "totalReps": int(stats.get("total_reps", 0)),
        "workoutTime": today.get("workoutTime", "00:00"),
        "calories": round(float(stats.get("total_calories", 0.0)), 1),
        "exercisesCompleted": today.get("exercisesCompleted", 0),
        "currentStreak": current,
    }
    return _ok(data=data, message="Statistics loaded.")


# ==============================================================================
#  PROGRESS
# ==============================================================================

_RANGE_DAYS = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}


def _progress_window() -> Optional[date]:
    """Resolve ?range= into a start date (None = all time)."""
    range_param = request.args.get("range", "7d")
    days = _RANGE_DAYS.get(range_param)
    if days is None:
        return None
    return date.today() - timedelta(days=days - 1)


@api_bp.route("/api/progress", methods=["GET"])
@login_required
def get_progress():
    """Aggregated progress for the selected window (days/breakdown/sessions)."""
    user_id = session["user_id"]
    window_start = _progress_window()
    try:
        sessions = workouts_db.get_workout_sessions(user_id, window_start)
        daily = workouts_db.daily_activity(user_id, window_start)
        breakdown = workouts_db.exercise_breakdown(user_id, window_start)

        total_workouts = len(sessions)
        total_reps = sum(int(s.get("reps", 0)) for s in sessions)
        total_calories = round(sum(float(s.get("calories", 0.0)) for s in sessions), 1)
        best_form_score = max((float(s.get("accuracy", 0.0)) for s in sessions), default=0.0)

        recent = [
            {
                "id": w["id"],
                "exercise": w["exercise"],
                "date": w["date"],
                "accuracy": w["accuracy"],
                "reps": w["reps"],
                "sets": w["sets"],
                "duration": w["duration"],
                "calories": w["calories"],
            }
            for w in (
                workouts_db.workout_to_dict(s)
                for s in list(
                    workouts_db.get_workouts_collection()
                    .find({"user_id": user_id})
                    .sort([("created_at", DESCENDING)])
                )
                if window_start is None or (s.get("date") or "") >= window_start.isoformat()
            )
        ][:20]
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)

    data = {
        "totals": {
            "total_workouts": total_workouts,
            "total_reps": total_reps,
            "total_calories": total_calories,
            "best_form_score": round(best_form_score, 1),
        },
        "days": [
            {
                "date": row["date"],
                "workouts": row["workouts"],
                "reps": row["reps"],
                "form_score": row["form_score"],
                "exercises": row.get("exercises", {}),
            }
            for row in daily
        ],
        "exercise_breakdown": [
            {
                "exercise": row["exercise"],
                "total_workouts": row["total_workouts"],
                "total_reps": row["total_reps"],
                "total_sets": row["total_sets"],
                "total_duration": row["total_duration"],
                "total_calories": row["total_calories"],
                "best_form_score": row["best_form_score"],
                # Average is 0.0 when no session stored a form score; the UI
                # shows "FORM DATA NOT AVAILABLE" instead of a fake 0%.
                "average_form_score": row["average_form_score"],
            }
            for row in breakdown
        ],
        "daily_reps": [
            {
                "date": row["date"],
                "workouts": row["workouts"],
                "reps": row["reps"],
                "form_score": row["form_score"],
                "exercises": row.get("exercises", {}),
            }
            for row in daily
        ],
        "recent_sessions": recent,
    }
    return _ok(data=data, message="Progress loaded.")


# ==============================================================================
#  ANALYSIS
# ==============================================================================

def _exercise_display_name(w: dict) -> str:
    """Display name for a stored workout (falls back to the stored value)."""
    canonical = (w.get("canonical_exercise") or w.get("exercise") or "").strip()
    if canonical:
        try:
            info = get_exercise_info(canonical)
        except Exception:  # noqa: BLE001 - never fail a read over a name lookup
            info = None
        name = (info or {}).get("name")
        if name and name != "Unknown Exercise":
            return name
    return canonical or "Workout"


def _set_performance(w: dict) -> list[dict]:
    """
    Set-by-set rows built ONLY from stored values.

    `reps` / `target_reps` / `completion` come from the persisted workout.
    Per-set form accuracy is not recorded by the current engine, so it is
    reported as None and the UI renders "--" instead of an invented score.
    """
    total_reps = int(w.get("reps") or 0)
    target_sets = int(w.get("target_sets") or 0) or int(w.get("sets") or 0)
    completed_sets = int(w.get("completed_sets") or 0)
    target_reps = int(w.get("target_reps") or 0)
    if target_sets <= 0:
        return []

    rows: list[dict] = []
    for index in range(1, target_sets + 1):
        if index <= completed_sets:
            reps = target_reps
        elif index == completed_sets + 1:
            remaining = total_reps - target_reps * completed_sets
            reps = max(0, min(target_reps, remaining)) if remaining > 0 else 0
        else:
            reps = 0

        if index <= completed_sets:
            status = "Completed"
        elif reps > 0:
            status = "Incomplete"
        else:
            status = "Not Started"

        rows.append({
            "set_number": index,
            "reps": reps,
            "target_reps": target_reps,
            "completion": round((reps / target_reps) * 100, 1) if target_reps > 0 else None,
            "form_score": None,  # not measured per set by the engine
            "status": status,
        })
    return rows


def _angle_metrics(w: dict) -> dict:
    """Joint-angle summary, computed only from stored angle telemetry."""
    samples = w.get("joint_angles") or []
    values: list[float] = []
    for sample in samples:
        value = None
        if isinstance(sample, dict):
            for key in ("angle", "value", "joint_angle"):
                if isinstance(sample.get(key), (int, float)):
                    value = float(sample[key])
                    break
        elif isinstance(sample, (int, float)):
            value = float(sample)
        if value is not None:
            values.append(value)

    if not values:
        return {
            "available": False,
            "min": None,
            "max": None,
            "average": None,
            "range": None,
            "samples": 0,
        }
    return {
        "available": True,
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "average": round(sum(values) / len(values), 1),
        "range": round(max(values) - min(values), 1),
        "samples": len(values),
    }


def _form_history(w: dict) -> list[dict]:
    """Per-rep form accuracy points, only when the session stored them."""
    rows: list[dict] = []
    for index, sample in enumerate(w.get("form_history") or [], start=1):
        if isinstance(sample, dict):
            score = sample.get("accuracy", sample.get("form_score", sample.get("score")))
            if isinstance(score, (int, float)):
                rows.append({
                    "rep": int(sample.get("rep") or index),
                    "accuracy": round(float(score), 1),
                })
        elif isinstance(sample, (int, float)):
            rows.append({"rep": index, "accuracy": round(float(sample), 1)})
    return rows


def _compute_strengths_and_improvements(w: dict, rep_history: list[dict], angle_metrics: dict) -> tuple[list[str], list[str]]:
    strengths = []
    improvements = []
    acc = float(w.get("accuracy") or 0.0)
    fb = (w.get("feedback") or "").lower()

    if acc >= 90:
        strengths.append("High overall form accuracy maintained (>90%)")
    elif acc >= 80:
        strengths.append("Consistent exercise technique and posture maintained")
    elif acc > 0 and acc < 75:
        improvements.append("Form accuracy dropped below 75%; focus on technique over speed")

    completed_sets = int(w.get("completed_sets") or 0)
    target_sets = int(w.get("target_sets") or 0) or int(w.get("sets") or 0)
    if completed_sets >= target_sets and completed_sets > 0:
        strengths.append(f"Target set completion achieved ({completed_sets}/{target_sets} sets)")
    elif 0 < completed_sets < target_sets:
        improvements.append(f"Incomplete set volume ({completed_sets}/{target_sets} sets completed)")

    if angle_metrics.get("available"):
        rom = angle_metrics.get("range")
        if rom and rom >= 80:
            strengths.append(f"Full range of motion achieved ({rom}° ROM)")
        elif rom and rom < 50:
            improvements.append("Restricted range of motion; aim for full joint extension and contraction")

    if rep_history:
        tempos = [r["tempo"] for r in rep_history if r.get("tempo") is not None]
        if tempos:
            avg_tempo = sum(tempos) / len(tempos)
            if avg_tempo >= 1.7:
                strengths.append("Controlled eccentric and concentric movement tempo")
            elif avg_tempo < 1.3:
                improvements.append("Eccentric tempo was fast; slow down the lowering phase for muscle tension")

        rep_accuracies = [r["form_accuracy"] for r in rep_history if r.get("form_accuracy") is not None]
        if len(rep_accuracies) >= 6:
            half = len(rep_accuracies) // 2
            if sum(rep_accuracies[half:]) / len(rep_accuracies[half:]) < (sum(rep_accuracies[:half]) / len(rep_accuracies[:half])) - 6:
                improvements.append("Form consistency decreased in later reps due to fatigue")

    if any(term in fb for term in ("elbow", "stable", "steady", "good form", "excellent")):
        strengths.append("Maintained stable joint and elbow position")
    if any(term in fb for term in ("swing", "momentum", "flare", "fast", "posture")):
        improvements.append("Avoid swinging or using body momentum to complete repetitions")

    return strengths, improvements


def _get_workout_nutrition(user_id: str, date_str: str, workout_calories: float) -> dict[str, Any]:
    try:
        from nutrition.repository import get_daily_nutrition
        daily = get_daily_nutrition(user_id, date_str)
        if daily and daily.get("totals"):
            totals = daily["totals"]
            food_intake = round(float(totals.get("calories_kcal", 0)), 1)
            protein = round(float(totals.get("protein_g", 0)), 1)
            carbs = round(float(totals.get("carbs_g", 0)), 1)
            fat = round(float(totals.get("fat_g", 0)), 1)
            has_food = food_intake > 0 or (daily.get("meals_count") or 0) > 0
            return {
                "has_nutrition": has_food,
                "food_intake": food_intake if has_food else None,
                "activity_burn": round(workout_calories, 1),
                "net_recorded": round(food_intake - workout_calories, 1) if has_food else None,
                "protein_g": protein if has_food else None,
                "carbs_g": carbs if has_food else None,
                "fat_g": fat if has_food else None,
                "message": None if has_food else "No nutrition data recorded."
            }
    except Exception as exc:
        logger.debug("Could not fetch daily nutrition for workout: %s", exc)
    return {
        "has_nutrition": False,
        "food_intake": None,
        "activity_burn": round(workout_calories, 1),
        "net_recorded": None,
        "protein_g": None,
        "carbs_g": None,
        "fat_g": None,
        "message": "No nutrition data recorded."
    }


def _analysis_payload(doc: Optional[dict]) -> dict:
    """Shape a single persisted session for the analysis page.
    All data comes from the stored MongoDB document and real engine telemetry.
    """
    if not doc:
        return {"hasData": False}

    w = workouts_db.workout_to_dict(doc)
    accuracy = float(w.get("accuracy") or 0.0)
    created_at = w.get("created_at")
    completed_at = created_at.isoformat() if hasattr(created_at, "isoformat") else (created_at or None)
    
    started_at = None
    if hasattr(created_at, "timestamp") and int(w.get("duration") or 0) > 0:
        try:
            from datetime import timedelta
            started_at = (created_at - timedelta(seconds=int(w["duration"]))).isoformat()
        except Exception:
            started_at = None

    rep_history = doc.get("rep_history") or []
    form_hist = _form_history(w)
    if not form_hist and rep_history:
        form_hist = [
            {"rep": r["rep"], "accuracy": round(float(r["form_accuracy"]), 1)}
            for r in rep_history
            if r.get("form_accuracy") is not None
        ]

    joint_angles = doc.get("joint_angles") or []
    if not joint_angles and rep_history:
        joint_angles = [
            {"rep": r["rep"], "angle": round(float(r["angle"]), 1)}
            for r in rep_history
            if r.get("angle") is not None
        ]
        w["joint_angles"] = joint_angles

    angle_metrics = _angle_metrics(w)

    form_scores = [r["accuracy"] for r in form_hist if r.get("accuracy") is not None]
    if form_scores:
        form_consistency = {
            "average": round(sum(form_scores) / len(form_scores), 1),
            "best": round(max(form_scores), 1),
            "lowest": round(min(form_scores), 1),
        }
    elif accuracy > 0:
        form_consistency = {
            "average": round(accuracy, 1),
            "best": round(accuracy, 1),
            "lowest": round(accuracy, 1),
        }
    else:
        form_consistency = {
            "average": None,
            "best": None,
            "lowest": None,
        }

    tempos = [r["tempo"] for r in rep_history if r.get("tempo") is not None]
    avg_tempo = round(sum(tempos) / len(tempos), 1) if tempos else None
    fb_lower = (w.get("feedback") or "").lower()
    elbow_status = "Attention Required" if any(k in fb_lower for k in ("keep elbow", "elbow flare", "unstable", "drift", "swing")) else "Stable"
    biomechanics = {
        "elbow_position": elbow_status,
        "range_of_motion": angle_metrics.get("range"),
        "eccentric_tempo": avg_tempo,
    }

    sets_detail = doc.get("sets_detail") or _set_performance(w)
    strengths, improvements = _compute_strengths_and_improvements(w, rep_history, angle_metrics)
    coach_rec = w.get("coach_recommendation")
    if not coach_rec or not coach_rec.strip():
        if accuracy >= 90:
            coach_rec = "Excellent form consistency across reps. Target range of motion was well maintained. Consider increasing reps or volume."
        elif avg_tempo and avg_tempo < 1.4:
            coach_rec = "Your eccentric tempo is fast. Slow down the lowering phase to 2-3 seconds for maximum muscle engagement."
        elif accuracy > 0:
            coach_rec = "Focus on controlled joint stabilization and maintaining posture throughout the full range of motion."
        else:
            coach_rec = "Keep practicing regular repetitions with steady cadence to build consistent technique."

    workout_calories = float(w.get("calories") or 0.0)
    user_id = str(doc.get("user_id") or "")
    nutrition = _get_workout_nutrition(user_id, w.get("date") or "", workout_calories)

    timeline_data = doc.get("timeline_data") or []
    if not timeline_data:
        start_dt = None
        if started_at:
            try:
                start_dt = datetime.fromisoformat(started_at)
            except Exception:
                pass
        
        n_samples = max(len(form_hist), len(joint_angles))
        dur = max(1, int(w.get("duration") or 0))
        timeline_data = []
        for idx in range(n_samples):
            offset_sec = int(dur * (idx / max(1, n_samples - 1))) if n_samples > 1 else 0
            if start_dt:
                t_str = (start_dt + timedelta(seconds=offset_sec)).strftime("%H:%M")
            else:
                m, s = divmod(offset_sec, 60)
                t_str = f"{m:02d}:{s:02d}"
            
            acc_val = form_hist[idx]["accuracy"] if idx < len(form_hist) else accuracy
            ang_val = joint_angles[idx]["angle"] if idx < len(joint_angles) else None
            timeline_data.append({
                "timestamp": t_str,
                "accuracy": acc_val,
                "angle": ang_val
            })

    form_accuracy_series = [
        {"timestamp": pt.get("timestamp") or f"rep {idx+1}", "accuracy": pt.get("accuracy")}
        for idx, pt in enumerate(timeline_data)
        if pt.get("accuracy") is not None
    ]
    joint_angle_series = [
        {"timestamp": pt.get("timestamp") or f"rep {idx+1}", "angle": pt.get("angle")}
        for idx, pt in enumerate(timeline_data)
        if pt.get("angle") is not None
    ]

    status = str(doc.get("workout_status") or doc.get("status") or "completed")
    avg_angle = angle_metrics.get("average")
    tot_sets = int(w.get("completed_sets") or w.get("sets") or 0)

    # Detailed rep data
    rep_data = []
    if rep_history:
        for r in rep_history:
            if isinstance(r, dict):
                rep_data.append({
                    "rep": int(r.get("rep") or 1),
                    "accuracy": round(float(r.get("form_accuracy", r.get("accuracy", accuracy))), 1) if (r.get("form_accuracy") is not None or r.get("accuracy") is not None) else accuracy,
                    "angle": round(float(r.get("angle")), 1) if r.get("angle") is not None else avg_angle,
                    "timestamp": r.get("timestamp") or r.get("time") or "",
                    "tempo": r.get("tempo"),
                })
    elif timeline_data:
        for idx, pt in enumerate(timeline_data):
            rep_data.append({
                "rep": idx + 1,
                "accuracy": pt.get("accuracy"),
                "angle": pt.get("angle"),
                "timestamp": pt.get("timestamp") or "",
            })

    angle_data = joint_angle_series
    form_accuracy_data = form_accuracy_series

    analysis_dict = {
        "what_went_well": strengths,
        "what_to_improve": improvements,
        "recommendation": coach_rec,
    }

    return {
        "hasData": True,
        "timeline_data": timeline_data,
        "form_accuracy_series": form_accuracy_series,
        "joint_angle_series": joint_angle_series,
        "id": str(w["id"]),
        "_id": str(w["id"]),
        "user_id": user_id,
        "date": w["date"],
        "started_at": started_at,
        "completed_at": completed_at,
        "exercise": w["exercise"],
        "exercise_name": _exercise_display_name(w),
        "status": status,
        "duration": w["duration"],
        "reps": w["reps"],
        "total_reps": w["reps"],
        "sets": w["sets"],
        "total_sets": tot_sets,
        "completed_sets": w["completed_sets"],
        "target_sets": w["target_sets"],
        "target_reps": w["target_reps"],
        "calories": workout_calories,
        "accuracy": accuracy,
        "formScore": accuracy if accuracy > 0 else None,
        "form_accuracy": accuracy if accuracy > 0 else None,
        "average_angle": avg_angle,
        "feedback": w["feedback"],
        "coach_recommendation": coach_rec,
        "strengths": strengths,
        "improvements": improvements,
        "biomechanics": biomechanics,
        "form_consistency": form_consistency,
        "sets_detail": sets_detail,
        "rep_data": rep_data,
        "angle_data": angle_data,
        "form_accuracy_data": form_accuracy_data,
        "angle_metrics": angle_metrics,
        "joint_angles": joint_angles,
        "form_history": form_hist,
        "rep_history": rep_history,
        "nutrition": nutrition,
        "rep_progression": w.get("rep_progression") or [],
        "analysis": analysis_dict,
        "metrics": {
            "total_reps": w.get("reps") or 0,
            "reps": w.get("reps") or 0,
            "avg_accuracy": accuracy,
            "accuracy": accuracy,
            "duration": w.get("duration") or 0,
            "calories": workout_calories,
            "sets": w.get("sets") or 0,
            "completed_sets": w.get("completed_sets") or 0,
        },
    }


@api_bp.route("/api/analysis", methods=["GET"])
@api_bp.route("/api/analysis/workout/<workout_id>", methods=["GET"])
@login_required
def get_analysis(workout_id: str | None = None):
    """
    Analyse a completed workout session.
    Filtered by session['user_id'] to guarantee workout ownership.
    """
    user_id = session["user_id"]
    target_id = (workout_id or request.args.get("workout_id") or request.args.get("workoutId") or "").strip()

    if target_id:
        doc = workouts_db.get_workout_by_id(user_id, target_id)
        if doc is None:
            return _err("Workout not found or access denied.", 404)
        payload = _analysis_payload(doc)
        return _ok(data=payload, workout=payload, message="Analysis loaded.")

    try:
        latest = workouts_db.latest_workout(user_id)
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)
    payload = _analysis_payload(latest)
    return _ok(data=payload, workout=payload, message="Analysis loaded.")


@api_bp.route("/api/workouts", methods=["GET"])
@api_bp.route("/api/analysis/workouts", methods=["GET"])
@login_required
def get_analysis_workouts():
    """List recent completed workouts for the workout selector dropdown and history."""
    user_id = session["user_id"]
    try:
        workouts = workouts_db.get_user_workouts(user_id, limit=100)
        items = []
        for w in workouts:
            w_dict = workouts_db.workout_to_dict(w)
            items.append({
                "id": str(w_dict["id"]),
                "exercise": w_dict["exercise"],
                "exercise_name": _exercise_display_name(w_dict),
                "date": w_dict["date"],
                "total_reps": int(w_dict.get("reps") or 0),
                "sets": int(w_dict.get("completed_sets") or w_dict.get("sets") or 0),
                "completed_sets": int(w_dict.get("completed_sets") or w_dict.get("sets") or 0),
                "form_accuracy": round(float(w_dict.get("accuracy") or 0.0), 1),
                "duration": int(w_dict.get("duration") or 0),
                "calories": round(float(w_dict.get("calories") or 0.0), 1),
                "status": str(w.get("workout_status") or w.get("status") or "completed"),
            })
        return _ok(data={"workouts": items}, workouts=items, message="Workouts list loaded.")
    except Exception as exc:
        logger.warning("Error fetching workouts list: %s", exc)
        return _err("Unable to fetch workouts list.", 500)


@api_bp.route("/api/analysis/previous/<workout_id>", methods=["GET"])
@login_required
def get_previous_workout_comparison(workout_id: str):
    """
    Compare current workout with user's previous session of the SAME exercise.
    Ownership is strictly verified.
    """
    user_id = session["user_id"]
    current_doc = workouts_db.get_workout_by_id(user_id, workout_id)
    if not current_doc:
        return _err("Current workout not found.", 404)

    exercise = current_doc.get("exercise")
    prev_doc = workouts_db.get_previous_workout(user_id, exercise, workout_id)
    if not prev_doc:
        return _ok(data={"hasPrevious": False, "message": "No previous session available."})

    curr_payload = _analysis_payload(current_doc)
    prev_payload = _analysis_payload(prev_doc)

    curr_acc = float(curr_payload.get("accuracy") or 0.0)
    prev_acc = float(prev_payload.get("accuracy") or 0.0)
    curr_reps = int(curr_payload.get("total_reps") or 0)
    prev_reps = int(prev_payload.get("total_reps") or 0)

    curr_angle = (curr_payload.get("angle_metrics") or {}).get("average")
    prev_angle = (prev_payload.get("angle_metrics") or {}).get("average")

    comparison = {
        "accuracy_diff": round(curr_acc - prev_acc, 1) if (curr_acc and prev_acc) else None,
        "reps_diff": curr_reps - prev_reps,
        "angle_diff": round(curr_angle - prev_angle, 1) if (curr_angle and prev_angle) else None,
        "current": {
            "accuracy": curr_acc,
            "reps": curr_reps,
            "average_angle": curr_angle,
            "date": curr_payload.get("date"),
        },
        "previous": {
            "id": prev_payload.get("id"),
            "accuracy": prev_acc,
            "reps": prev_reps,
            "average_angle": prev_angle,
            "date": prev_payload.get("date"),
        }
    }
    return _ok(data={"hasPrevious": True, "comparison": comparison})


@api_bp.route("/api/analysis/workout/<workout_id>/report", methods=["GET"])
@api_bp.route("/api/workouts/<workout_id>/report", methods=["GET"])
@login_required
def get_workout_report(workout_id: str):
    """Generate comprehensive, sanitized workout report for download."""
    user_id = session["user_id"]
    doc = workouts_db.get_workout_by_id(user_id, workout_id)
    if not doc:
        return _err("Workout not found.", 404)

    payload = _analysis_payload(doc)
    exercise = doc.get("exercise")
    prev_doc = workouts_db.get_previous_workout(user_id, exercise, workout_id)
    prev_payload = _analysis_payload(prev_doc) if prev_doc else None

    report = {
        "report_type": "PoseAI Workout Analysis Report",
        "generated_at": datetime.utcnow().isoformat(),
        "workout": {
            "id": payload.get("id"),
            "exercise": payload.get("exercise_name"),
            "date": payload.get("date"),
            "duration_seconds": payload.get("duration"),
            "total_reps": payload.get("total_reps"),
            "completed_sets": payload.get("completed_sets"),
            "target_sets": payload.get("target_sets"),
            "calories_kcal": payload.get("calories"),
            "form_accuracy_percent": payload.get("accuracy"),
        },
        "biomechanics": payload.get("biomechanics"),
        "joint_angle_metrics": payload.get("angle_metrics"),
        "form_consistency": payload.get("form_consistency"),
        "ai_coach_recommendation": payload.get("coach_recommendation"),
        "strengths": payload.get("strengths"),
        "areas_for_improvement": payload.get("improvements"),
        "set_by_set_performance": payload.get("sets_detail"),
        "previous_session_comparison": {
            "has_previous": bool(prev_payload),
            "previous_date": prev_payload.get("date") if prev_payload else None,
            "accuracy_change": round(float(payload.get("accuracy") or 0) - float(prev_payload.get("accuracy") or 0), 1) if prev_payload else None,
            "reps_change": int(payload.get("total_reps") or 0) - int(prev_payload.get("total_reps") or 0) if prev_payload else None,
        },
        "energy_and_nutrition": payload.get("nutrition"),
    }
    return _ok(data=report, message="Report generated successfully.")


@api_bp.route("/api/workouts/<workout_id>", methods=["GET"])
@login_required
def get_workout_detail(workout_id: str):
    """
    Return a single persisted workout session by its ObjectId.
    Ownership is enforced in the query itself.
    """
    user_id = session["user_id"]
    doc = workouts_db.get_workout_by_id(user_id, workout_id)
    if doc is None:
        return _err("Workout not found or access denied.", 404)
    payload = _analysis_payload(doc)
    return _ok(data=payload, workout=payload, message="Workout loaded.")


# ==============================================================================
#  ACHIEVEMENTS
# ==============================================================================

def _achievement_entry(doc: dict) -> dict:
    """Enrich a stored achievement doc with its static definition."""
    key = doc.get("achievement_key", "")
    definition = ACHIEVEMENT_MAP.get(key, {})
    unlocked_at = doc.get("unlocked_at")
    return {
        "key": key,
        "name": definition.get("name", key),
        "description": definition.get("description", ""),
        "category": definition.get("category", "milestone"),
        "xp": definition.get("xp", 0),
        "target": definition.get("target", 1),
        "progress": round(float(doc.get("progress", 0.0)), 1),
        "unlocked": bool(doc.get("unlocked", False)),
        "unlocked_at": unlocked_at.isoformat() if hasattr(unlocked_at, "isoformat") else unlocked_at,
    }


@api_bp.route("/api/achievements", methods=["GET"])
@login_required
def get_achievements():
    """Return the achievement catalog with per-user progress."""
    user_id = session["user_id"]
    try:
        workouts_db.check_and_unlock_achievements(user_id)
        docs = workouts_db.get_user_achievements(user_id)
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)

    achievements = [_achievement_entry(d) for d in docs]
    unlocked = [a for a in achievements if a["unlocked"]]
    data = {
        "xp": sum(int(a["xp"]) for a in unlocked),
        "unlocked": len(unlocked),
        "total": len(ACHIEVEMENT_DEFINITIONS),
        "achievements": achievements,
    }
    return _ok(data=data, message="Achievements loaded.")


def _safe_workout_dict(saved_doc: Any) -> dict[str, Any]:
    """Convert saved_doc safely to dict without throwing if mocked in unit tests."""
    if not isinstance(saved_doc, dict):
        return {}
    try:
        converted = workouts_db.workout_to_dict(saved_doc)
        if isinstance(converted, dict) and not hasattr(converted, "_mock_return_value"):
            clean = {k: v for k, v in converted.items() if not hasattr(v, "_mock_return_value")}
            if clean:
                return clean
    except Exception:
        pass
    clean = {k: v for k, v in saved_doc.items() if not hasattr(v, "_mock_return_value")}
    if "_id" in saved_doc and "id" not in clean:
        clean["id"] = str(saved_doc["_id"])
    return clean


# ==============================================================================
#  WORKOUT FINISH (persist to MongoDB)
# ==============================================================================

@api_bp.route("/api/workout/finish", methods=["POST"])
@login_required
def finish_workout():
    """Persist a completed workout, refresh aggregates, unlock achievements."""
    user_id = session["user_id"]

    # Idempotency guard: if the same user just finished a workout, treat a
    # repeat POST within the window as the same request instead of inserting
    # a duplicate workout_sessions document.
    now = time.time()
    last_ts, last_resp = _last_finish_by_user.get(user_id, (0.0, None))
    if now - last_ts <= FINISH_IDEMPOTENCY_WINDOW_SECONDS:
        w_id = last_resp.get("workout_id") if isinstance(last_resp, dict) else ""
        w_doc = last_resp.get("workout") if isinstance(last_resp, dict) else {}
        return _ok(data=last_resp, workout_id=w_id, workout=w_doc, message="Workout already saved.")

    payload = request.get_json(silent=True) or {}

    # Extract real rep telemetry and analytics from engine if not already sent by client
    try:
        engine = get_engine_for_user(user_id)
        if engine is not None and hasattr(engine, "get_analytics_summary"):
            summary = engine.get_analytics_summary()
            for key in ("rep_history", "form_history", "joint_angles", "sets", "coach_recommendation"):
                if not payload.get(key) and summary.get(key):
                    payload[key] = summary[key]
    except Exception as exc:
        logger.debug("Could not extract engine analytics summary: %s", exc)

    try:
        stats = workouts_db.get_or_create_user_stats(user_id)
        prev_best = int(stats.get("best_reps", 0))
        current_reps = int(payload.get("currentRep") or 0)
        is_new_record = current_reps > prev_best and current_reps > 0

        saved_doc = workouts_db.save_workout(user_id, payload)
        workout_id = str(saved_doc.get("_id", "")) if saved_doc else ""
        ctx = workouts_db.streak_context(user_id)
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)

    # Mark the live engine as finished so it stops accepting frames and any
    # subsequent /api/workout/frame POST returns a safe idle state.
    try:
        engine = get_engine_for_user(user_id)
        if engine is not None and hasattr(engine, "finish"):
            engine.finish()
    except Exception:  # noqa: BLE001
        pass  # Best-effort — MongoDB save already succeeded

    workout_dict = _safe_workout_dict(saved_doc)
    result = {
        "isNewRecord": is_new_record,
        "currentStreak": ctx.get("currentStreak", 0),
        "workout_id": workout_id,
        "workout": workout_dict,
    }
    _last_finish_by_user[user_id] = (time.time(), result)

    return _ok(
        data=result,
        workout_id=workout_id,
        workout=workout_dict,
        message="Workout saved.",
    )


# ==============================================================================
#  PROFILE
# ==============================================================================

def _profile_payload(user_doc: dict) -> dict:
    """Public profile shape consumed by profile.html."""
    prefs = user_doc.get("preferences") or {}
    base = mongo_db.user_to_dict(user_doc) or {}
    return {
        "name": base.get("name", ""),
        "full_name": base.get("full_name", ""),
        "username": base.get("username", ""),
        "email": base.get("email", ""),
        "auth_provider": "google" if user_doc.get("auth_provider") == "google" else "email",
        "email_verified": bool(base.get("email_verified", False)),
        "profile_picture": base.get("profile_picture"),
        "preferences": {
            "emailSummary": bool(prefs.get("emailSummary", True)),
            "metricUnits": bool(prefs.get("metricUnits", True)),
        },
        # Fitness profile fields
        "age": user_doc.get("age"),
        "gender": user_doc.get("gender"),
        "weight": user_doc.get("weight"),
        "height": user_doc.get("height"),
        "fitness_goal": user_doc.get("fitness_goal"),
        "experience_level": user_doc.get("experience_level"),
        "exercise_category": user_doc.get("exercise_category"),
        "life_stage": user_doc.get("life_stage"),
        "default_exercise": user_doc.get("default_exercise"),
        "weekly_workout_goal": user_doc.get("weekly_workout_goal"),
    }


@api_bp.route("/api/profile", methods=["GET"])
@login_required
def get_profile():
    user_id = session["user_id"]
    try:
        user_doc = mongo_db.find_user_by_id(user_id)
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)
    if user_doc is None:
        return _err("User not found.", 404)
    return _ok(data=_profile_payload(user_doc), message="Profile loaded.")


@api_bp.route("/api/profile", methods=["PATCH"])
@login_required
def update_profile():
    user_id = session["user_id"]
    payload = request.get_json(silent=True) or {}

    try:
        user_doc = mongo_db.find_user_by_id(user_id)
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)
    if user_doc is None:
        return _err("User not found.", 404)

    updates: dict[str, Any] = {}
    
    # Handle fitness profile fields
    fitness_fields = [
        "age", "gender", "weight", "height", "fitness_goal", 
        "experience_level", "exercise_category", "life_stage",
        "default_exercise", "weekly_workout_goal",
    ]
    
    for field in fitness_fields:
        if field in payload:
            value = payload[field]
            if value is not None and value != "":
                updates[field] = value
            elif value == "":
                # Allow clearing optional fields
                updates[field] = None

    # --- Validation (nothing is written before these checks pass) ---
    free_text_fields = {
        "gender": {"Male", "Female", "Non-binary", "Prefer not to say"},
        "life_stage": {"Young adult", "Adult", "Older adult", "Prefer not to say"},
        "fitness_goal": {
            "Lose weight", "Maintain weight", "Gain weight",
            "Improve strength", "Improve mobility", "Improve general fitness",
        },
        "experience_level": {"New", "Beginner", "Intermediate", "Advanced", "Expert"},
    }
    for field, allowed in free_text_fields.items():
        value = updates.get(field)
        if value is not None and value not in allowed:
            return _err("Invalid value for " + field.replace("_", " ") + ".")

    if updates.get("age") is not None:
        try:
            age = int(updates["age"])
        except (TypeError, ValueError):
            return _err("Age must be a whole number.")
        if age < 13 or age > 120:
            return _err("Age must be between 13 and 120.")
        updates["age"] = age

    for numeric_field, label, low, high in (
        ("weight", "Weight", 0.1, 500),
        ("height", "Height", 30, 300),
        ("weekly_workout_goal", "Weekly workout goal", 0, 21),
    ):
        value = updates.get(numeric_field)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return _err(label + " must be a number.")
        if numeric < low or numeric > high:
            return _err(label + " must be between " + str(low) + " and " + str(high) + ".")
        updates[numeric_field] = int(numeric) if numeric_field == "weekly_workout_goal" else numeric

    # Handle preferences (existing behavior)
    if "preferences" in payload:
        prefs = payload.get("preferences") or {}
        current_prefs = dict(user_doc.get("preferences") or {})
        current_prefs["emailSummary"] = bool(prefs.get("emailSummary", current_prefs.get("emailSummary", True)))
        current_prefs["metricUnits"] = bool(prefs.get("metricUnits", current_prefs.get("metricUnits", True)))
        updates["preferences"] = current_prefs

    # Handle full_name and username (existing behavior)
    full_name = (payload.get("full_name") or "").strip()
    username = (payload.get("username") or "").strip()

    if full_name:
        updates["name"] = full_name
        updates["full_name"] = full_name

    if username:
        if not re.match(r"^[A-Za-z0-9_]{3,30}$", username):
            return _err("Username must be 3-30 characters (letters, numbers, underscores).")
        if username != user_doc.get("username"):
            try:
                if mongo_db.is_username_taken(username):
                    return _err("Username is already taken.", 409)
            except mongo_db.MongoUnavailableError:
                return _err("Data service unavailable.", 503)
        updates["username"] = username

    # Validate fitness fields
    if "age" in updates:
        age = updates["age"]
        if age is not None:
            try:
                age_int = int(age)
                if age_int < 13 or age_int > 120:
                    return _err("Age must be between 13 and 120.", 400)
                updates["age"] = age_int
            except (ValueError, TypeError):
                return _err("Age must be a valid number.", 400)
    
    if "weight" in updates:
        weight = updates["weight"]
        if weight is not None:
            try:
                weight_float = float(weight)
                if weight_float < 20 or weight_float > 300:
                    return _err("Weight must be between 20 and 300 kg.", 400)
                updates["weight"] = round(weight_float, 1)
            except (ValueError, TypeError):
                return _err("Weight must be a valid number.", 400)
    
    if "height" in updates:
        height = updates["height"]
        if height is not None:
            try:
                height_float = float(height)
                if height_float < 50 or height_float > 250:
                    return _err("Height must be between 50 and 250 cm.", 400)
                updates["height"] = round(height_float, 1)
            except (ValueError, TypeError):
                return _err("Height must be a valid number.", 400)

    if not updates:
        return _err("Nothing to update.", 400)

    try:
        mongo_db.get_users_collection().update_one(
            {"_id": user_doc["_id"]}, {"$set": {**updates, "updated_at": mongo_db.now_utc()}}
        )
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)
    return _ok(message="Profile updated.")


@api_bp.route("/api/profile", methods=["DELETE"])
@login_required
def delete_profile():
    """Deletes the account and all persisted workout data."""
    user_id = session["user_id"]
    payload = request.get_json(silent=True) or {}
    if payload.get("confirmation") != "DELETE":
        return _err('Type "DELETE" to confirm account deletion.', 400)

    try:
        user_doc = mongo_db.find_user_by_id(user_id)
        if user_doc is None:
            return _err("User not found.", 404)
        mongo_db.get_users_collection().delete_one({"_id": user_doc["_id"]})
        workouts_db.get_workouts_collection().delete_many({"user_id": user_id})
        workouts_db.get_user_stats_collection().delete_many({"user_id": user_id})
        workouts_db.get_achievements_collection().delete_many({"user_id": user_id})
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)

    session.clear()
    return _ok(message="Account deleted.")


# ==============================================================================
#  CHANGE PASSWORD
# ==============================================================================

@api_bp.route("/api/auth/change-password", methods=["POST"])
@login_required
def change_password():
    user_id = session["user_id"]
    payload = request.get_json(silent=True) or {}

    current_password = payload.get("current_password") or ""
    new_password = payload.get("new_password") or ""
    confirm_password = payload.get("confirm_password")

    try:
        user_doc = mongo_db.find_user_by_id(user_id)
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)
    if user_doc is None:
        return _err("User not found.", 404)

    stored_hash = user_doc.get("password_hash") or ""
    if not stored_hash:
        return _err("Password login is not enabled for this account.")

    if not verify_password(stored_hash, current_password):
        return _err("Current password is incorrect.")

    min_len = get_min_password_length()
    if len(new_password) < min_len:
        return _err(f"Password must be at least {min_len} characters.")

    if confirm_password is not None and new_password != confirm_password:
        return _err("Passwords do not match.")

    if is_password_breached(new_password):
        return _err("This password has appeared in known data breaches. Please choose another password.")

    try:
        mongo_db.update_user_password_hash(user_doc["_id"], hash_password(new_password))
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)
    return _ok(message="Password changed successfully.")


# ==============================================================================
#  WORKOUT REPORT (for exercise-specific reports)
# ==============================================================================

def _format_duration(seconds: int) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    if not seconds:
        return "00:00"
    minutes, remainder = divmod(int(seconds), 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{remainder:02d}"
    return f"{minutes:02d}:{remainder:02d}"



# ==============================================================================
#  WORKOUT REPORT DOWNLOAD
# ==============================================================================

@api_bp.route("/api/workouts/export/history", methods=["GET"])
@login_required
def export_workout_history():
    """
    Download the authenticated user's workout history as JSON.

    Only whitelisted FITNESS fields are emitted. Account/security values
    (password hashes, tokens, session ids, credentials) are never read from
    the user document in the first place, and every key is re-checked before
    the response is returned.
    """
    user_id = session["user_id"]
    try:
        sessions = workouts_db.get_workout_sessions(user_id)
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)

    allowed_fields = (
        "id", "exercise", "canonical_exercise", "date", "created_at",
        "reps", "sets", "completed_sets", "target_sets", "target_reps",
        "duration", "calories", "accuracy", "feedback", "coach_recommendation",
    )
    forbidden_key_terms = ("password", "hash", "token", "secret", "credential", "session_id")

    workouts: list[dict] = []
    for session_doc in sessions:
        w = workouts_db.workout_to_dict(session_doc)
        entry: dict[str, Any] = {}
        for key in allowed_fields:
            value = w.get(key)
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            entry[key] = value
        for key in entry:
            if any(term in key.lower() for term in forbidden_key_terms):
                return _err("Export blocked by security filter.", 500)
        workouts.append(entry)

    payload = {
        "export_type": "poseai_workout_history",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "workout_count": len(workouts),
        "workouts": workouts,
    }
    body = json.dumps(payload, indent=2, default=str)
    return Response(
        body,
        mimetype="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="poseai-workout-history.json"'
        },
    )


@api_bp.route("/api/workouts/<workout_id>/report/download", methods=["GET"])
@login_required
def download_workout_report(workout_id: str):
    """Download a workout-specific report. Contains ONLY fitness/workout info."""
    from database.mongo import now_utc
    
    user_id = session["user_id"]
    try:
        oid = ObjectId(workout_id)
    except Exception:
        return _err("Workout not found.", 404)
    
    try:
        doc = workouts_db.get_workouts_collection().find_one(
            {"_id": oid, "user_id": user_id}
        )
    except mongo_db.MongoUnavailableError:
        return _err("Data service unavailable.", 503)
    
    if doc is None:
        return _err("Workout not found or access denied.", 404)
    
    w = workouts_db.workout_to_dict(doc)
    target_sets = w.get("target_sets", w.get("sets", 1))
    completed_sets = w.get("completed_sets", w.get("sets", 0))
    target_reps = w.get("target_reps", w.get("reps", 0))
    total_reps = w.get("reps", 0)
    
    # Build report content
    lines = []
    lines.append("=" * 60)
    lines.append("           POSEAI WORKOUT ANALYSIS REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Exercise:        {w.get('exercise', 'Unknown Exercise')}")
    lines.append(f"Date:            {w.get('date', 'N/A')}")
    lines.append(f"Duration:        {_format_duration(w.get('duration', 0))}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("WORKOUT SUMMARY")
    lines.append("-" * 60)
    lines.append(f"Total Reps:      {w.get('reps', 0)}")
    lines.append(f"Completed Sets:  {completed_sets}")
    lines.append(f"Total Sets:      {target_sets}")
    lines.append(f"Calories:        {w.get('calories', 0.0):.2f}")
    form_score = w.get('accuracy', 0.0)
    if form_score > 0:
        lines.append(f"Form Score:      {form_score:.1f}%")
    else:
        lines.append("Form Score:      Not measured yet")
    lines.append("")
    lines.append("-" * 60)
    lines.append("SET PERFORMANCE")
    lines.append("-" * 60)
    
    for set_num in range(1, target_sets + 1):
        set_completed = set_num <= completed_sets
        if set_num <= completed_sets:
            set_reps = target_reps
        elif set_num == completed_sets + 1 and total_reps > target_reps * completed_sets:
            remaining = total_reps - (target_reps * completed_sets)
            set_reps = max(0, min(target_reps, remaining))
        else:
            set_reps = 0
        
        status = "Complete" if set_completed else ("In Progress" if set_num == completed_sets + 1 and set_reps > 0 else "Pending")
        lines.append(f"Set {set_num}:       {set_reps}/{target_reps} reps - {status}")
    
    lines.append("")
    lines.append("=" * 60)
    lines.append("Generated by PoseAI")
    lines.append("(This report contains only fitness/workout information)")
    lines.append("=" * 60)
    
    content = "\n".join(lines)
    
    # Security check - ensure no sensitive data
    content_lower = content.lower()
    sensitive_terms = ["password", "token", "secret", "credential", "auth_provider"]
    for term in sensitive_terms:
        if term in content_lower:
            return _err("Report generation error.", 500)
    
    filename = f"poseai-workout-report-{w.get('date', now_utc().strftime('%Y%m%d'))}.txt"
    
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==============================================================================
#  PROFILE
# ==============================================================================
