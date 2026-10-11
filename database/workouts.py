"""
PoseAI — MongoDB Workouts Layer

Persists completed workout sessions, per-user aggregates, and achievement
progress in MongoDB. This is the migration target for the workout data
that previously lived in SQLAlchemy (WorkoutSession / UserStats /
UserAchievement).

It shares the single `database.mongo` connection, so in dev mode
(MONGO_ALLOW_MOCK=1) it transparently reads/writes the in-memory mongomock
database used by the auth tests.

Storage contract (all `user_id` values are the hex ObjectId string from the
Flask session):
    workout_sessions:  {
        "_id": ObjectId, "user_id": str, "exercise": str, "reps": int,
        "sets": int, "duration": int, "calories": float, "accuracy": float,
        "feedback": str, "date": "YYYY-MM-DD", "created_at": datetime(UTC),
    }
    user_stats:        {
        "_id": ObjectId, "user_id": str, "total_workouts": int,
        "total_reps": int, "total_sets": int, "total_calories": float,
        "total_duration": int, "current_streak": int, "longest_streak": int,
        "last_workout_date": "YYYY-MM-DD"|None, "best_reps": int,
        "best_calories": float, "best_duration": int,
        "best_form_score": float, "updated_at": datetime(UTC),
    }
    user_achievements: {
        "_id": ObjectId, "user_id": str, "achievement_key": str,
        "unlocked": bool, "progress": float, "unlocked_at": datetime|None,
    }

Dates are stored as ISO date strings ("YYYY-MM-DD") so range queries and
lexicographic comparisons behave chronologically without extra conversion.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta, datetime
from typing import Any, Optional

from pymongo import ASCENDING, DESCENDING

from database import mongo as mongo_db
from models import ACHIEVEMENT_DEFINITIONS, ACHIEVEMENT_MAP

logger = logging.getLogger("poseai.workouts")

INDEXES_ENSURED = False


def _ensure_indexes(database: Any) -> None:
    """Create indexes backing the workout collections. Best-effort."""
    try:
        database["workout_sessions"].create_index(
            [("user_id", ASCENDING), ("date", ASCENDING)]
        )
        database["user_stats"].create_index([("user_id", ASCENDING)], unique=True)
        database["user_achievements"].create_index(
            [("user_id", ASCENDING), ("achievement_key", ASCENDING)], unique=True
        )
    except Exception:  # noqa: BLE001 - index creation is best-effort
        logger.warning("Could not create workout indexes (best-effort).")


def _db() -> Any:
    global INDEXES_ENSURED
    database = mongo_db.get_db()
    if not INDEXES_ENSURED:
        _ensure_indexes(database)
        INDEXES_ENSURED = True
    return database


def get_workouts_collection() -> Any:
    return _db()["workout_sessions"]


def get_user_stats_collection() -> Any:
    return _db()["user_stats"]


def get_achievements_collection() -> Any:
    return _db()["user_achievements"]


def _parse_date(value: Any) -> Optional[date]:
    """Parse a stored ISO date string (or date/datetime) into a date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


# ==============================================================================
# SERIALIZATION
# ==============================================================================

def workout_to_dict(doc: dict) -> dict:
    """Mirror the old WorkoutSession.to_dict() shape for API responses.

    Only exposes fitness/workout data - never password, tokens, session
    secrets or other account-internal fields.
    """
    if not doc:
        return {}
    return {
        "id": str(doc.get("_id", "")),
        "user_id": doc.get("user_id", ""),  # kept for internal use only
        "exercise": doc.get("exercise", ""),
        "canonical_exercise": doc.get("canonical_exercise", doc.get("exercise", "")),
        "reps": int(doc.get("reps", 0) or 0),
        "sets": int(doc.get("sets", 0) or 0),
        "completed_sets": int(doc.get("completed_sets", doc.get("sets", 0)) or 0),
        "target_sets": int(doc.get("target_sets", doc.get("sets", 0)) or 0),
        "target_reps": int(doc.get("target_reps", doc.get("goal_reps", 15)) or 0),
        "duration": int(doc.get("duration", 0) or 0),
        "calories": round(float(doc.get("calories", 0.0) or 0.0), 2),
        "accuracy": round(float(doc.get("accuracy", 0.0) or 0.0), 2),
        "feedback": doc.get("feedback", "") or "",
        "date": doc.get("date", ""),
        "stage_transitions": doc.get("stage_transitions", []) or [],
        "joint_angles": doc.get("joint_angles", []) or [],
        "form_history": doc.get("form_history", []) or [],
        "rep_progression": doc.get("rep_progression", []) or [],
        "analysis": doc.get("analysis", {}) or {},
        "coach_recommendation": doc.get("coach_recommendation", "") or "",
        "created_at": doc.get("created_at", ""),
        # Battle Mode fields (None/0 for regular workouts)
        "game_mode": doc.get("game_mode"),
        "battle_result": doc.get("battle_result"),
        "best_combo": int(doc.get("best_combo", 0) or 0),
        "damage_dealt": int(doc.get("damage_dealt", 0) or 0),
    }


def stats_to_dict(doc: dict) -> dict:
    """Mirror the old UserStats.to_dict() shape for API responses."""
    return {
        "total_workouts": doc.get("total_workouts", 0),
        "total_reps": doc.get("total_reps", 0),
        "total_sets": doc.get("total_sets", 0),
        "total_calories": round(doc.get("total_calories", 0.0), 1),
        "total_duration": doc.get("total_duration", 0),
        "current_streak": doc.get("current_streak", 0),
        "longest_streak": doc.get("longest_streak", 0),
        "last_workout_date": doc.get("last_workout_date"),
        "best_reps": doc.get("best_reps", 0),
        "best_calories": round(doc.get("best_calories", 0.0), 1),
        "best_duration": doc.get("best_duration", 0),
        "best_form_score": round(doc.get("best_form_score", 0.0), 1),
    }


# ==============================================================================
# USER STATS
# ==============================================================================

def get_or_create_user_stats(user_id: str) -> dict:
    """Return the user_stats document for a user, creating an empty one if needed."""
    coll = get_user_stats_collection()
    doc = coll.find_one({"user_id": user_id})
    if doc is None:
        doc = {
            "user_id": user_id,
            "total_workouts": 0,
            "total_reps": 0,
            "total_sets": 0,
            "total_calories": 0.0,
            "total_duration": 0,
            "current_streak": 0,
            "longest_streak": 0,
            "last_workout_date": None,
            "best_reps": 0,
            "best_calories": 0.0,
            "best_duration": 0,
            "best_form_score": 0.0,
            "updated_at": datetime.utcnow(),
        }
        coll.insert_one(doc)
    return doc


def _set_user_stats(user_id: str, updates: dict) -> None:
    updates = dict(updates)
    updates["updated_at"] = datetime.utcnow()
    get_user_stats_collection().update_one(
        {"user_id": user_id}, {"$set": updates}
    )


# ==============================================================================
# STREAK
# ==============================================================================

def calculate_streak_for_user(
    user_id: str, today: date | None = None
) -> tuple[int, int, bool, date | None]:
    """
    Calculate a user's workout streak from their persisted workout_sessions
    dates. This is the single source of truth for streak data.

    Semantics (Section 8 of the streak spec):
      - A day counts toward the streak only if a workout was COMPLETED
        (a workout_sessions doc was created via /api/workout/finish).
      - Multiple workout sessions on the same day count as one day.
      - The "current streak" is the *alive* streak:
          * If today is completed, count back from today.
          * Else if yesterday is completed, the streak is still alive
            (it is displayed as-is but never increments on rest days).
          * Otherwise the streak is 0.
      - The longest streak is the longest run of consecutive days ever
        recorded and NEVER decreases.

    Returns (current, longest, today_completed, last_workout_date).
    """
    sessions = list(
        get_workouts_collection().find({"user_id": user_id}, {"date": 1})
    )
    unique_dates = sorted(
        {
            d
            for s in sessions
            if (d := _parse_date(s.get("date"))) is not None
        }
    )
    if not unique_dates:
        return 0, 0, False, None

    today = today or date.today()
    date_set = set(unique_dates)

    if today in date_set:
        anchor = today
    elif (today - timedelta(days=1)) in date_set:
        anchor = today - timedelta(days=1)
    else:
        anchor = None

    current_streak = 0
    if anchor is not None:
        d = anchor
        while d in date_set:
            current_streak += 1
            d -= timedelta(days=1)

    longest_streak = 0
    streak = 0
    prev_date = None
    for d in unique_dates:
        if prev_date is None:
            streak = 1
        elif (d - prev_date).days == 1:
            streak += 1
        else:
            streak = 1
        prev_date = d
        longest_streak = max(longest_streak, streak)

    return current_streak, longest_streak, today in date_set, unique_dates[-1]


def streak_context(user_id: str) -> dict[str, Any]:
    """
    Recompute a user's streak from their workout_sessions history (the
    authoritative source), sync the cached user_stats values, and return
    the canonical streak payload. Called on every read endpoint so the
    streak is always correct even after rest days.
    """
    current, longest, today_completed, last_date = calculate_streak_for_user(user_id)
    stats = get_or_create_user_stats(user_id)

    longest_streak = max(longest, stats.get("longest_streak", 0))
    new_last = last_date.isoformat() if last_date is not None else None
    updates: dict[str, Any] = {
        "current_streak": current,
        "longest_streak": longest_streak,
    }
    if new_last is not None and (stats.get("last_workout_date") is None or new_last > stats.get("last_workout_date")):
        updates["last_workout_date"] = new_last
    _set_user_stats(user_id, updates)

    return {
        "currentStreak": current,
        "longestStreak": longest_streak,
        "todayCompleted": today_completed,
        "lastWorkoutDate": new_last,
    }


# ==============================================================================
# WORKOUT SESSIONS + STATS UPDATE
# ==============================================================================

def update_user_stats(user_id: str, workout_doc: dict, today: date | None = None) -> None:
    """Update the user_stats aggregates after a workout session is completed."""
    stats = get_or_create_user_stats(user_id)

    total_workouts = int(stats.get("total_workouts", 0)) + 1
    total_reps = int(stats.get("total_reps", 0)) + int(workout_doc.get("reps", 0))
    total_sets = int(stats.get("total_sets", 0)) + int(workout_doc.get("sets", 0))
    total_calories = float(stats.get("total_calories", 0.0)) + float(workout_doc.get("calories", 0.0))
    total_duration = int(stats.get("total_duration", 0)) + int(workout_doc.get("duration", 0))

    rev = int(workout_doc.get("reps", 0))
    cal = float(workout_doc.get("calories", 0.0))
    dur = int(workout_doc.get("duration", 0))
    acc = float(workout_doc.get("accuracy", 0.0))

    best_reps = max(int(stats.get("best_reps", 0)), rev)
    best_calories = max(float(stats.get("best_calories", 0.0)), cal)
    best_duration = max(int(stats.get("best_duration", 0)), dur)
    best_form_score = max(float(stats.get("best_form_score", 0.0)), acc)

    current, longest, _, _ = calculate_streak_for_user(user_id, today)
    longest_streak = max(longest, int(stats.get("longest_streak", 0)))

    workout_date = _parse_date(workout_doc.get("date"))
    last_workout_date = workout_date.isoformat() if workout_date is not None else None
    if stats.get("last_workout_date") is not None and (
        last_workout_date is None or stats.get("last_workout_date") > last_workout_date
    ):
        last_workout_date = stats.get("last_workout_date")

    _set_user_stats(user_id, {
        "total_workouts": total_workouts,
        "total_reps": total_reps,
        "total_sets": total_sets,
        "total_calories": total_calories,
        "total_duration": total_duration,
        "current_streak": current,
        "longest_streak": longest_streak,
        "last_workout_date": last_workout_date,
        "best_reps": best_reps,
        "best_calories": best_calories,
        "best_duration": best_duration,
        "best_form_score": best_form_score,
    })


# ==============================================================================
# ACHIEVEMENTS
# ==============================================================================

def check_and_unlock_achievements(user_id: str) -> list[dict]:
    """
    Check all achievement definitions against user stats and unlock any
    newly earned achievements. Returns a list of newly unlocked achievement
    dicts (old UserAchievement.to_dict() shape).
    """
    stats = get_or_create_user_stats(user_id)
    newly_unlocked = []

    progress_map = {
        "first_rep": int(stats.get("total_reps", 0)),
        "first_workout": int(stats.get("total_workouts", 0)),
        "workouts_5": int(stats.get("total_workouts", 0)),
        "workouts_10": int(stats.get("total_workouts", 0)),
        "workouts_50": int(stats.get("total_workouts", 0)),
        "reps_50": int(stats.get("total_reps", 0)),
        "reps_100": int(stats.get("total_reps", 0)),
        "reps_500": int(stats.get("total_reps", 0)),
        "reps_1000": int(stats.get("total_reps", 0)),
        "streak_3": int(stats.get("current_streak", 0)),
        "streak_7": int(stats.get("current_streak", 0)),
        "streak_30": int(stats.get("current_streak", 0)),
        "calorie_burn_100": float(stats.get("total_calories", 0.0)),
        "calorie_burn_500": float(stats.get("total_calories", 0.0)),
        "form_master": float(stats.get("best_form_score", 0.0)),
        "consistency_king": int(stats.get("total_workouts", 0)),
    }

    coll = get_achievements_collection()

    for defn in ACHIEVEMENT_DEFINITIONS:
        key = defn["key"]
        target = defn["target"]
        current_progress = progress_map.get(key, 0)

        ua = coll.find_one({"user_id": user_id, "achievement_key": key})

        if ua is None:
            ua = {
                "user_id": user_id,
                "achievement_key": key,
                "progress": 0.0,
                "unlocked": False,
                "unlocked_at": None,
            }
            inserted = coll.insert_one(ua)
            ua["_id"] = inserted.inserted_id

        if ua.get("unlocked"):
            continue

        ua["progress"] = min(100.0, (current_progress / target) * 100) if target > 0 else 0.0

        if current_progress >= target:
            ua["unlocked"] = True
            ua["unlocked_at"] = datetime.utcnow()
            coll.update_one(
                {"_id": ua["_id"]},
                {"$set": {"progress": ua["progress"], "unlocked": True, "unlocked_at": ua["unlocked_at"]}},
            )
            newly_unlocked.append(_achievement_to_dict(ua))
        else:
            coll.update_one(
                {"_id": ua["_id"]},
                {"$set": {"progress": ua["progress"]}},
            )

    return newly_unlocked


def _achievement_to_dict(ua: dict) -> dict:
    definition = ACHIEVEMENT_MAP.get(ua.get("achievement_key"), {})
    unlocked_at = ua.get("unlocked_at")
    return {
        "key": ua.get("achievement_key"),
        "name": definition.get("name", ua.get("achievement_key")),
        "description": definition.get("description", ""),
        "category": definition.get("category", "milestone"),
        "xp": definition.get("xp", 0),
        "target": definition.get("target", 1),
        "progress": ua.get("progress", 0.0),
        "unlocked": ua.get("unlocked", False),
        "unlocked_at": unlocked_at.isoformat() if hasattr(unlocked_at, "isoformat") else unlocked_at,
    }


def get_user_achievements(user_id: str) -> list[dict]:
    """Return every achievement doc for a user (for the API response)."""
    return list(get_achievements_collection().find({"user_id": user_id}))


# ==============================================================================
# SAVE WORKOUT (the /api/workout/finish persist path)
# ==============================================================================

def save_workout(user_id: str, payload: dict) -> dict:
    """
    Create and persist a workout_sessions document from the finish payload.
    Also updates user_stats and checks achievements. Returns the stored doc.
    """
    raw_exercise = payload.get("exercise_name") or payload.get("exercise") or "Unknown"
    exercise = canonical_exercise_name(raw_exercise) if raw_exercise != "Unknown" else "Unknown"
    # "currentRep" is the reps of the ACTIVE set (engine contract). When the
    # caller also sends the session total (web UI does) we store that, so a
    # 3x15 workout is recorded as 45 reps rather than the last set's 15.
    set_reps = payload.get("currentRep") or 0
    payload_total_reps = payload.get("total_reps")
    if isinstance(payload_total_reps, (int, float)) and payload_total_reps > 0:
        total_reps = int(payload_total_reps)
    else:
        total_reps = int(set_reps)
    total_sets = payload.get("currentSet") or 0
    calories = payload.get("calories") or 0.0
    feedback = payload.get("feedback") or ""
    
    # Store additional analytics data if provided
    analysis = payload.get("analysis") or {}
    coach_recommendation = payload.get("coach_recommendation") or ""
    stage_transitions = payload.get("stage_transitions") or []
    joint_angles = payload.get("joint_angles") or []
    form_history = payload.get("form_history") or []
    rep_progression = payload.get("rep_progression") or []
    # Set metrics: never invent them. When the caller does not send an
    # explicit value we fall back to the set counter the engine reported.
    completed_sets = payload.get("completed_sets")
    if completed_sets is None:
        completed_sets = total_sets
    target_sets = payload.get("target_sets")
    if target_sets is None:
        target_sets = total_sets
    target_reps = payload.get("target_reps")
    if target_reps is None:
        target_reps = int(payload.get("goalRep") or 0) or int(set_reps) or 0
    
    workout_time_str = payload.get("workoutTime") or "00:00"
    duration_seconds = 0
    explicit_duration = payload.get("duration")
    if isinstance(explicit_duration, (int, float)) and explicit_duration > 0:
        duration_seconds = int(explicit_duration)
    elif isinstance(workout_time_str, str) and ":" in workout_time_str:
        parts = workout_time_str.split(":")
        try:
            duration_seconds = int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            duration_seconds = 0
    
    accuracy = 0.0
    explicit_accuracy = payload.get("accuracy")
    if isinstance(explicit_accuracy, (int, float)) and explicit_accuracy > 0:
        accuracy = min(100.0, max(0.0, float(explicit_accuracy)))
    elif payload.get("form_accuracy"):
        try:
            accuracy = float(payload.get("form_accuracy"))
        except (ValueError, TypeError):
            accuracy = 0.0
    
    rep_history = payload.get("rep_history") or []
    sets_detail = payload.get("sets_detail") or payload.get("sets") or []

    if accuracy <= 0.0:
        if form_history:
            scores = [float(f.get("accuracy", 0)) for f in form_history if isinstance(f, dict) and f.get("accuracy")]
            if scores:
                accuracy = round(sum(scores) / len(scores), 1)
        elif rep_history:
            scores = [float(r.get("form_accuracy", 0)) for r in rep_history if isinstance(r, dict) and r.get("form_accuracy")]
            if scores:
                accuracy = round(sum(scores) / len(scores), 1)

    doc = {
        "user_id": user_id,
        "exercise": exercise,
        "canonical_exercise": exercise,
        "reps": int(total_reps),
        "sets": int(total_sets),
        "completed_sets": int(completed_sets),
        "target_sets": int(target_sets),
        "target_reps": int(target_reps),
        "duration": duration_seconds,
        "calories": float(calories),
        "accuracy": float(accuracy),
        "feedback": feedback,
        "date": date.today().isoformat(),
        "created_at": datetime.utcnow(),
        "analysis": analysis,
        "coach_recommendation": coach_recommendation,
        "stage_transitions": stage_transitions,
        "joint_angles": joint_angles,
        "form_history": form_history,
        "rep_progression": rep_progression,
        "rep_history": rep_history,
        "sets_detail": sets_detail,
        "timeline_data": payload.get("timeline_data") or [],
    }

    # Battle Mode extras: stored ONLY when the caller (game.html) sends them.
    # Regular workouts keep the exact same document shape as before.
    game_mode = payload.get("game_mode")
    if game_mode:
        doc["game_mode"] = str(game_mode)
        if payload.get("battle_result"):
            doc["battle_result"] = str(payload["battle_result"])
        doc["best_combo"] = int(payload.get("best_combo") or 0)
        doc["damage_dealt"] = int(payload.get("damage_dealt") or 0)
        if payload.get("workout_status"):
            # Battle Mode: "completed" on victory, "partial" on defeat/manual
            # finish — the workout is never deleted, only labelled.
            doc["workout_status"] = str(payload["workout_status"])

    coll = get_workouts_collection()
    result = coll.insert_one(doc)
    doc["_id"] = result.inserted_id
    
    update_user_stats(user_id, doc)
    check_and_unlock_achievements(user_id)
    
    return doc


def get_workout_by_id(user_id: str, workout_id: str) -> Optional[dict]:
    """Fetch single workout session enforcing user_id ownership."""
    from bson import ObjectId
    try:
        oid = ObjectId(workout_id)
        query = {"_id": oid, "user_id": user_id}
    except Exception:
        query = {"_id": workout_id, "user_id": user_id}
    return get_workouts_collection().find_one(query)


def get_previous_workout(user_id: str, exercise: str, current_workout_id: str | None = None) -> Optional[dict]:
    """
    Find the most recent completed workout for this user matching the SAME exercise,
    excluding the current workout session.
    """
    from bson import ObjectId
    query: dict[str, Any] = {
        "user_id": user_id,
        "exercise": exercise,
    }
    if current_workout_id:
        try:
            oid = ObjectId(current_workout_id)
            query["_id"] = {"$ne": oid}
        except Exception:
            query["_id"] = {"$ne": current_workout_id}

    return get_workouts_collection().find_one(
        query,
        sort=[("created_at", DESCENDING), ("date", DESCENDING)]
    )


def get_user_workouts(user_id: str, limit: int = 50) -> list[dict]:
    """Fetch list of completed workouts for user selector, newest first."""
    return list(
        get_workouts_collection()
        .find({"user_id": user_id})
        .sort([("created_at", DESCENDING), ("date", DESCENDING)])
        .limit(limit)
    )


# ==============================================================================
# QUERIES
# ==============================================================================

def get_workout_sessions(user_id: str, start_date: date | None = None) -> list[dict]:
    """Return a user's workout docs ordered by date ascending (oldest first)."""
    query: dict[str, Any] = {"user_id": user_id}
    if start_date is not None:
        query["date"] = {"$gte": start_date.isoformat()}
    return list(
        get_workouts_collection().find(query).sort([("date", ASCENDING), ("created_at", ASCENDING)])
    )


def latest_workout(user_id: str) -> Optional[dict]:
    """Return the most recent completed workout doc for a user, if any."""
    return get_workouts_collection().find_one(
        {"user_id": user_id}, sort=[("created_at", DESCENDING)]
    )


def today_performance(user_id: str) -> dict[str, Any]:
    """
    Aggregate today's completed workouts for the dashboard's "Today's
    Performance" card. Computed purely from MongoDB (ground truth), so the
    numbers survive engine / server restarts and remain correct even when
    the engine (main.py) is offline.
    """
    today_iso = date.today().isoformat()
    sessions = list(
        get_workouts_collection().find({"user_id": user_id, "date": today_iso})
    )
    total_reps = sum(int(s.get("reps", 0)) for s in sessions)
    total_calories = round(sum(float(s.get("calories", 0.0)) for s in sessions), 1)
    total_seconds = sum(int(s.get("duration", 0)) for s in sessions)

    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        workout_time = f"{hours}:{minutes:02d}:{seconds:02d}"
    elif minutes or seconds:
        workout_time = f"{minutes:02d}:{seconds:02d}"
    else:
        workout_time = "00:00"

    return {
        "totalReps": total_reps,
        "workoutTime": workout_time,
        "calories": total_calories,
        "exercisesCompleted": len(sessions),
        "workoutsToday": len(sessions),
    }


def canonical_exercise_name(name: str | None) -> str:
    """Normalize exercise naming variations (e.g. 'BICEP CURL', 'bicep_curl' -> 'Bicep Curl')."""
    if not name:
        return "Workout"
    cleaned = str(name).strip()
    if not cleaned:
        return "Workout"

    lookup = {
        "bicep curl": "Bicep Curl",
        "bicep_curl": "Bicep Curl",
        "bicepcurls": "Bicep Curl",
        "bicep curls": "Bicep Curl",
        "squat": "Squat",
        "squats": "Squat",
        "goblet squat": "Goblet Squat",
        "goblet_squat": "Goblet Squat",
        "pushup": "Push-up",
        "push up": "Push-up",
        "push-up": "Push-up",
        "push_up": "Push-up",
        "pushups": "Push-up",
        "shoulder press": "Shoulder Press",
        "shoulder_press": "Shoulder Press",
        "triceps pushdown": "Triceps Pushdown",
        "tricep pushdown": "Triceps Pushdown",
        "triceps_pushdown": "Triceps Pushdown",
        "jumping jacks": "Jumping Jacks",
        "jumping_jacks": "Jumping Jacks",
        "lunges": "Lunges",
        "lunge": "Lunges",
        "plank": "Plank",
    }
    lowered = cleaned.lower()
    if lowered in lookup:
        return lookup[lowered]
    lowered_hyphen = lowered.replace("-", " ")
    if lowered_hyphen in lookup:
        return lookup[lowered_hyphen]
    lowered_underscore = lowered.replace("_", " ")
    if lowered_underscore in lookup:
        return lookup[lowered_underscore]

    words = [w.capitalize() for w in cleaned.replace("_", " ").split()]
    return " ".join(words) if words else "Workout"


def exercise_breakdown(user_id: str, start_date: date | None = None) -> list[dict[str, Any]]:
    """Aggregate completed workouts per exercise from stored sessions."""
    sessions = get_workout_sessions(user_id, start_date)
    groups: dict[str, dict[str, Any]] = {}
    for s in sessions:
        raw_exercise = s.get("exercise_name") or s.get("exercise") or "Workout"
        exercise = canonical_exercise_name(raw_exercise)
        entry = groups.setdefault(exercise, {
            "exercise": exercise,
            "total_workouts": 0,
            "total_reps": 0,
            "total_sets": 0,
            "total_calories": 0.0,
            "total_duration": 0,
            "best_reps": 0,
            "best_form_score": 0.0,
            "accuracy_sum": 0.0,
        })
        entry["total_workouts"] += 1
        entry["total_reps"] += int(s.get("reps", 0))
        entry["total_sets"] += int(s.get("sets", 0))
        entry["total_calories"] += float(s.get("calories", 0.0))
        entry["total_duration"] += int(s.get("duration", 0))
        entry["best_reps"] = max(entry["best_reps"], int(s.get("reps", 0)))
        acc = float(s.get("accuracy", 0.0))
        entry["best_form_score"] = max(entry["best_form_score"], acc)
        entry["accuracy_sum"] += acc

    results: list[dict[str, Any]] = []
    for entry in groups.values():
        n = int(entry["total_workouts"])
        results.append({
            "exercise": entry["exercise"],
            "total_workouts": n,
            "total_reps": entry["total_reps"],
            "total_sets": entry["total_sets"],
            "total_calories": round(entry["total_calories"], 1),
            "total_duration": entry["total_duration"],
            "best_reps": entry["best_reps"],
            "best_form_score": round(entry["best_form_score"], 1),
            "average_form_score": round(entry["accuracy_sum"] / n, 1) if n else 0.0,
        })
    results.sort(key=lambda e: int(e["total_reps"]), reverse=True)
    return results


def average_form_score(user_id: str, start_date: date | None = None) -> float:
    """Average persisted form score across a user's sessions (0.0 if none)."""
    sessions = get_workout_sessions(user_id, start_date)
    if not sessions:
        return 0.0
    total = sum(float(s.get("accuracy", 0.0)) for s in sessions)
    return round(total / len(sessions), 1)


def daily_activity(user_id: str, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
    """Aggregate a user's stored sessions into per-day rows (date ascending)."""
    sessions = get_workout_sessions(user_id, start_date)
    accumulated: dict[str, dict[str, Any]] = {}
    for s in sessions:
        day = _parse_date(s.get("date"))
        if day is None:
            continue
        if end_date is not None and day > end_date:
            continue
        key = day.isoformat()
        entry = accumulated.setdefault(key, {
            "date": key,
            "reps": 0,
            "sets": 0,
            "calories": 0.0,
            "duration": 0,
            "workouts": 0,
            "accuracy_sum": 0.0,
            "exercises": {},
        })
        reps_done = int(s.get("reps", 0))
        entry["reps"] += reps_done
        entry["sets"] += int(s.get("sets", 0))
        entry["calories"] += float(s.get("calories", 0.0))
        entry["duration"] += int(s.get("duration", 0))
        entry["workouts"] += 1
        entry["accuracy_sum"] += float(s.get("accuracy", 0.0))
        raw_ex_name = (s.get("exercise_name") or s.get("exercise") or "Workout").strip()
        ex_name = canonical_exercise_name(raw_ex_name)
        if ex_name:
            entry["exercises"][ex_name] = entry["exercises"].get(ex_name, 0) + reps_done

    rows: list[dict[str, Any]] = []
    for entry in accumulated.values():
        n = int(entry["workouts"])
        entry["form_score"] = round(entry.pop("accuracy_sum") / n, 1) if n else 0.0
        entry["calories"] = round(entry["calories"], 1)
        rows.append(entry)
    rows.sort(key=lambda r: str(r["date"]))

    # Zero-fill the requested window so charts render a complete range
    # (one bar/tick per day) instead of only the days that had sessions.
    # Empty days keep form_score=None so no graph ever invents a 0% form.
    if start_date is not None and end_date is None:
        by_date = {r["date"]: r for r in rows}
        filled: list[dict[str, Any]] = []
        cursor = start_date
        today = date.today()
        while cursor <= today:
            key = cursor.isoformat()
            row = by_date.get(key)
            if row is None:
                filled.append({
                    "date": key,
                    "reps": 0,
                    "sets": 0,
                    "calories": 0.0,
                    "duration": 0,
                    "workouts": 0,
                    "form_score": None,
                    "exercises": {},
                })
            else:
                filled.append(row)
            cursor += timedelta(days=1)
        return filled
    return rows


def weekly_progress(user_id: str) -> list[int]:
    """
    Total reps for each of the last 7 days (oldest first) ending today.
    Drives the dashboard's weekly progress chart from persisted data.
    """
    today = date.today()
    start = today - timedelta(days=6)
    sessions = list(
        get_workouts_collection().find(
            {"user_id": user_id, "date": {"$gte": start.isoformat(), "$lte": today.isoformat()}}
        )
    )
    buckets = [0] * 7
    for session in sessions:
        session_date = _parse_date(session.get("date"))
        if session_date is None:
            continue
        index = (session_date - start).days
        if 0 <= index < 7:
            buckets[index] += int(session.get("reps", 0))
    return buckets