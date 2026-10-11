"""
TEMPORARY verification harness for the PoseAI UI/functional fixes.

Runs the real Flask app against the in-memory mongomock database used by the
existing test-suite (tests/helpers.py) and asserts the behaviour of every
changed area. Delete this file after reviewing the output.
"""

import json

from bson import ObjectId

from tests.helpers import setup_mongo_mock

setup_mongo_mock()

from app import app  # noqa: E402
from database import mongo as mongo_db  # noqa: E402

# Surface real tracebacks while verifying.
app.config["PROPAGATE_EXCEPTIONS"] = True

FAILURES = []


def check(label, condition, detail=""):
    print(("[PASS] " if condition else "[FAIL] ") + label + (" :: " + str(detail) if detail else ""))
    if not condition:
        FAILURES.append(label)


def make_user(email):
    """Insert a real user document and return its id string (like signup does)."""
    oid = ObjectId()
    mongo_db.get_users_collection().insert_one({
        "_id": oid,
        "email": email,
        "username": "",
        "name": "Verification Athlete",
        "full_name": "Verification Athlete",
        "password_hash": "irrelevant-for-this-check",
        "is_active": True,
        "preferences": {},
    })
    return str(oid)


def client_for(user_id):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["name"] = "Verification Athlete"
    return client


def main():
    client = client_for(make_user("verify-athlete-1@example.com"))

    # ---------------- 1. Page routes + static assets ----------------
    print("\n--- pages ---")
    for path in ("/", "/dashboard", "/workout", "/analysis", "/progress", "/profile", "/exercises", "/achievements", "/game"):
        resp = client.get(path)
        check("GET " + path, resp.status_code == 200, resp.status_code)

    shell = client.get("/js/shell.js").get_data(as_text=True)
    check("GET /js/shell.js", "function boot()" in shell and "})();" in shell)
    check("More dropdown link -> /exercises (not .html)", 'href: "/exercises"' in shell)
    check("More dropdown link -> /achievements", 'href: "/achievements"' in shell)
    check("no stale .html links remain in nav", "exercises.html" not in shell and "achievements.html" not in shell)
    check("More menu is click-toggled (no group-hover)", "group-hover:block" not in shell)
    check("More active state computed", "MORE_ACTIVE" in shell)

    resp = client.get("/exercises.html")
    check("old broken href /exercises.html is not a route", resp.status_code == 404, resp.status_code)

    # ---------------- 1b. Game page (Battle Mode) ----------------
    print("\n--- game page ---")
    game_html = client.get("/game").get_data(as_text=True)
    check("GET /game -> 200", client.get("/game").status_code == 200)
    check("game.html loads shell.js (navbar + window.api)",
          '<script src="js/shell.js">' in game_html
          or '<script src="js/shell.js"></script>' in game_html
          or 'src="js/shell.js"' in game_html)
    check("game.html uses dynamic exercise grid",
          'id="exerciseCards"' in game_html and "cardsStatus" in game_html)
    for marker in (
        "loadExerciseCatalog",
        "buildExerciseCards",
        "setExerciseInfo",
        "normalizeEnginePayload",
        "renderEnginePayload",
        "continueFromSetModal",
        "saveBattle",
        "handleVictory",
        "handleDefeat",
        "state.exerciseInfo",
        "HERO_BASE_DAMAGE",
    ):
        check("game.html implements: " + marker, marker in game_html)
    check("game.html has no leftover JS-CHUNK marker", "JS-CHUNK" not in game_html)
    check("game.html ends properly", game_html.rstrip().endswith("</html>"))
    game_name_markers = ("Bicep Curl", "Push-up", "Squat", "Triceps Pushdown", "Lunges",
                         "Jumping Jacks", "Shoulder Press", "Burpees", "Warrior II",
                         "Goblet Squat", "Crossover Toe Touches")
    for name in game_name_markers:
        check("game fallback catalog has: " + name, name in game_html)

    # ---------------- 1c. Exercise catalog API ----------------
    print("\n--- /api/exercises ---")
    resp = client.get("/api/exercises")
    ex = resp.get_json()["data"]
    check("GET /api/exercises -> 200",
          resp.status_code == 200 and isinstance(ex, list) and len(ex) >= 11)
    keys = set()
    for entry in ex:
        for field in ("id", "name", "difficulty", "goal", "sets", "description", "muscles"):
            check("exercise entry carries " + field, entry.get(field) is not None, entry.get("name"))
        keys.add(str(entry["id"]))
        check("exercise goal is a positive int", isinstance(entry["goal"], int) and entry["goal"] > 0)
        check("exercise sets is a positive int", isinstance(entry["sets"], int) and entry["sets"] > 0)
    check("catalog covers engine keys 1-9,g,t",
          {"1", "2", "3", "4", "5", "6", "7", "8", "9", "g", "t"} <= keys, sorted(keys))

    analysis_html = client.get("/analysis").get_data(as_text=True)
    for marker in (
        "Performance Overview",
        "Form Accuracy Trend",
        "Set-by-Set Performance",
        "Joint Angle Analysis",
        "Form &amp; Technique",
        "AI Coach",
        "Session Details",
        "DOWNLOAD WORKOUT REPORT",
        "START YOUR FIRST WORKOUT",
    ):
        check("analysis.html contains: " + marker, marker in analysis_html)

    workout_html = client.get("/workout").get_data(as_text=True)
    for marker in (
        "setCompleteModal",
        "setCompletePct",
        "setCompleteNext",
        "doneTargetLine",
        "state.setModalOpen",
        "setCompleted",
        "reloadExercisesBtn",
        "READY",
    ):
        check("workout.html contains: " + marker, marker in workout_html)

    profile_html = client.get("/profile").get_data(as_text=True)
    for marker in (
        "Update Profile",
        "SAVE PROFILE",
        "fieldLifeStage",
        "EXPORT WORKOUT HISTORY (JSON)",
        "DOWNLOAD WORKOUT REPORT",
    ):
        check("profile.html contains: " + marker, marker in profile_html)

    # ---------------- 2. Empty analysis state ----------------
    print("\n--- empty states ---")
    resp = client.get("/api/analysis")
    check("GET /api/analysis with no workouts -> hasData False", resp.get_json()["data"]["hasData"] is False)

    resp = client.get("/api/progress?range=all")
    data = resp.get_json()["data"]
    check("progress with no workouts -> empty breakdown", data["exercise_breakdown"] == [])
    # ---------------- 3. Save a 3 x 15 workout ----------------
    print("\n--- finish workout (3 sets x 15 reps) ---")
    finish = client.post("/api/workout/finish", json={
        "exercise": "Bicep Curl",
        "currentRep": 15,          # reps of the ACTIVE (last) set
        "currentSet": 3,
        "total_reps": 45,          # engine session total
        "completed_sets": 3,
        "target_sets": 3,
        "target_reps": 15,
        "calories": 22.07,
        "workoutTime": "03:16",
        "feedback": "Good elbow control, keep it steady.",
        "accuracy": 0,             # the engine does not record form scores
    })
    body = finish.get_json()
    check("POST /api/workout/finish", finish.status_code == 200 and body["success"], body)
    workout_id = body["data"]["workout_id"]
    check("workout_id returned", bool(workout_id), workout_id)

    # ---------------- 4. Analysis payload ----------------
    print("\n--- analysis payload ---")
    resp = client.get("/api/analysis?workout_id=" + workout_id)
    d = resp.get_json()["data"]
    check("analysis by workout_id -> 200", resp.status_code == 200)
    check("exercise_name resolved", d["exercise_name"] == "Bicep Curl", d.get("exercise_name"))
    check("total_reps = 45 (session total, not last set)", d["total_reps"] == 45, d.get("total_reps"))
    check("completed_sets = 3", d["completed_sets"] == 3, d.get("completed_sets"))
    check("target_sets = 3", d["target_sets"] == 3, d.get("target_sets"))
    check("target_reps = 15", d["target_reps"] == 15, d.get("target_reps"))
    check("calories stored", abs(d["calories"] - 22.07) < 0.01, d.get("calories"))
    check("duration = 196s from 03:16", d["duration"] == 196, d.get("duration"))
    check("form_accuracy is None (not measured, not fake 0)", d["form_accuracy"] is None, d.get("form_accuracy"))
    check("formScore is None", d["formScore"] is None, d.get("formScore"))
    check("sets_detail has 3 rows", len(d["sets_detail"]) == 3, len(d["sets_detail"]))
    check("all 3 sets Completed",
          all(row["status"] == "Completed" for row in d["sets_detail"]),
          [row["status"] for row in d["sets_detail"]])
    check("set rows carry 15/15 with 100% completion",
          all(row["reps"] == 15 and row["completion"] == 100.0 for row in d["sets_detail"]))
    check("per-set form stays None (UI shows --)",
          all(row["form_score"] is None for row in d["sets_detail"]))
    check("angle_metrics not fabricated", d["angle_metrics"]["available"] is False, d["angle_metrics"])
    check("form_history empty (real telemetry absent)", d["form_history"] == [], d["form_history"])
    check("feedback is the stored string", d["feedback"].startswith("Good elbow control"))
    check("started_at derived from completed_at - duration", bool(d["started_at"]), d["started_at"])

    resp = client.get("/api/analysis")
    check("analysis without param uses latest workout",
          resp.get_json()["data"]["id"] == workout_id)

    # ---------------- 5. Progress aggregates ----------------
    print("\n--- progress ---")
    resp = client.get("/api/progress?range=all")
    data = resp.get_json()["data"]
    check("totals.total_reps = 45", data["totals"]["total_reps"] == 45, data["totals"])
    entry = data["exercise_breakdown"][0]
    check("breakdown exercise name", entry["exercise"] == "Bicep Curl", entry["exercise"])
    check("breakdown total_workouts = 1", entry["total_workouts"] == 1, entry["total_workouts"])
    check("breakdown total_reps = 45", entry["total_reps"] == 45, entry["total_reps"])
    check("breakdown calories real", abs(entry["total_calories"] - 22.1) < 0.2, entry["total_calories"])
    check("breakdown exposes average_form_score (0 = not measured)",
          entry["average_form_score"] == 0.0, entry["average_form_score"])
    check("breakdown exposes total_sets", entry["total_sets"] == 3, entry["total_sets"])
    check("recent_sessions has the workout", len(data["recent_sessions"]) == 1)
# ---------------- 6. Report download ----------------
    print("\n--- report download ---")
    resp = client.get("/api/workouts/" + workout_id + "/report/download")
    report = resp.get_data(as_text=True)
    check("report download 200", resp.status_code == 200, resp.status_code)
    check("report mentions POSEAI", "POSEAI" in report)
    check("report contains real total reps 45", "Total Reps:      45" in report,
          [line for line in report.splitlines() if "Total Reps" in line])
    check("report contains completed sets 3", "Completed Sets:  3" in report,
          [line for line in report.splitlines() if "Completed Sets" in line])
    low = report.lower()
    check("report has no password", "password" not in low)
    check("report has no token", "token" not in low)
    check("report labels unmeasured form honestly", "Not measured" in report)

    # ---------------- 7. Sanitised JSON history export ----------------
    print("\n--- workout history export ---")
    resp = client.get("/api/workouts/export/history")
    raw = resp.get_data(as_text=True)
    check("export 200", resp.status_code == 200, resp.status_code)
    check("export is an attachment",
          "attachment" in resp.headers.get("Content-Disposition", ""),
          resp.headers.get("Content-Disposition"))
    payload = json.loads(raw)
    allowed = {
        "id", "exercise", "canonical_exercise", "date", "created_at", "reps", "sets",
        "completed_sets", "target_sets", "target_reps", "duration", "calories",
        "accuracy", "feedback", "coach_recommendation",
    }
    keys = set()
    for workout in payload["workouts"]:
        keys |= set(workout.keys())
    check("export keys are whitelisted only", keys <= allowed, sorted(keys - allowed))
    check("export has the workout", payload["workout_count"] == 1, payload["workout_count"])
    for term in ("password", "token", "secret", "credential", "hash", "session_id", "auth_provider"):
        check("export contains no '" + term + "'", term not in raw.lower())

    # ---------------- 8. Profile update ----------------
    print("\n--- profile update ---")
    resp = client.patch("/api/profile", json={
        "full_name": "Verification Athlete",
        "username": "verify_athlete",
        "age": 27,
        "gender": "Prefer not to say",
        "life_stage": "Adult",
        "weight": 72.5,
        "height": 178,
        "weekly_workout_goal": 4,
        "fitness_goal": "Improve strength",
        "experience_level": "Intermediate",
        "exercise_category": "Bicep Curl",
        "default_exercise": "1",
    })
    check("PATCH /api/profile", resp.status_code == 200, resp.get_json())
    prof = client.get("/api/profile").get_json()["data"]
    check("age saved", prof["age"] == 27, prof.get("age"))
    check("gender saved", prof["gender"] == "Prefer not to say", prof.get("gender"))
    check("life_stage saved", prof["life_stage"] == "Adult", prof.get("life_stage"))
    check("weight saved", prof["weight"] == 72.5, prof.get("weight"))
    check("height saved", prof["height"] == 178, prof.get("height"))
    check("weekly_workout_goal saved", prof["weekly_workout_goal"] == 4, prof.get("weekly_workout_goal"))
    check("fitness_goal saved", prof["fitness_goal"] == "Improve strength", prof.get("fitness_goal"))
    check("experience_level saved", prof["experience_level"] == "Intermediate", prof.get("experience_level"))
    check("default_exercise saved", prof["default_exercise"] == "1", prof.get("default_exercise"))
    check("profile never exposes password_hash", "password_hash" not in prof)

    resp = client.patch("/api/profile", json={"fitness_goal": "Get swole fast"})
    check("invalid enum rejected with 400", resp.status_code == 400, resp.get_json())
    resp = client.patch("/api/profile", json={"weekly_workout_goal": 99})
    check("out-of-range weekly goal rejected", resp.status_code == 400, resp.get_json())
    resp = client.patch("/api/profile", json={"age": 5})
    check("out-of-range age rejected", resp.status_code == 400, resp.get_json())

    # ---------------- 9. Ownership isolation ----------------
    print("\n--- ownership ---")
    other = client_for(make_user("verify-athlete-2@example.com"))
    resp = other.get("/api/analysis?workout_id=" + workout_id)
    check("user B cannot read user A's workout (404)", resp.status_code == 404, resp.status_code)
    resp = other.get("/api/workouts/" + workout_id + "/report/download")
    check("user B cannot download user A's report (404)", resp.status_code == 404, resp.status_code)
    resp = other.get("/api/workouts/export/history")
    other_export = json.loads(resp.get_data(as_text=True)) if resp.status_code == 200 else {}
    check("user B export contains no workouts", other_export.get("workout_count", -1) == 0, other_export)

    # ---------------- 10. Engine set-completion contract ----------------
    print("\n--- engine set contract ---")
    src = open("core/web_workout_engine.py", encoding="utf-8").read()
    check("engine exposes set_completed", "set_completed" in src)
    check("engine completed_sets counts the finished set",
          '"completed_sets": self._current_set if set_completed else max(0, self._current_set - 1)' in src)

    # ---------------- 11. Battle Mode save contract ----------------
    print("\n--- battle save (game.html payload) ---")
    # The finish endpoint de-dupes repeat POSTs within a short window, and the
    # regular workout above already primed that guard. Clear it so this battle
    # POST is treated as a fresh workout, exactly like a later in-app session.
    from dashboard_api import _last_finish_by_user as _idem
    _idem.clear()
    battle = client.post("/api/workout/finish", json={
        "exercise": "Goblet Squat",        # selected from catalog key "g"
        "currentRep": 12,
        "currentSet": 3,
        "total_reps": 36,
        "completed_sets": 3,
        "target_sets": 3,
        "target_reps": 12,
        "calories": 18.4,
        "workoutTime": "02:10",
        "feedback": "Battle cleared the monster.",
        "accuracy": 0,
        "game_mode": "battle",
        "battle_result": "victory",
        "best_combo": 7,
        "damage_dealt": 456,
        "workout_status": "completed",
    })
    body = battle.get_json()
    check("battle finish -> 200 + success", battle.status_code == 200 and body["success"], body)
    battle_id = body["data"]["workout_id"]

    resp = client.get("/api/analysis?workout_id=" + battle_id)
    bd = resp.get_json()["data"]
    check("battle analysis resolves exercise_name", bd["exercise_name"] == "Goblet Squat", bd.get("exercise_name"))
    check("battle analysis real reps 36", bd["total_reps"] == 36, bd.get("total_reps"))
    check("battle form not measured (None)", bd["form_accuracy"] is None, bd.get("form_accuracy"))

    resp = client.get("/api/progress?range=all")
    data = resp.get_json()["data"]
    by_name = {e["exercise"]: e for e in data["exercise_breakdown"]}
    check("breakdown includes battle exercise",
          "Goblet Squat" in by_name and by_name["Goblet Squat"]["total_reps"] == 36,
          by_name.get("Goblet Squat"))
    check("regular + battle sessions both stored",
          data["totals"]["total_workouts"] == 2 and data["totals"]["total_reps"] == 81,
          data["totals"])

    # ---------------- 12. Daily activity zero-fill ----------------
    print("\n--- daily activity zero-fill ---")
    resp = client.get("/api/progress?range=7d")
    days = resp.get_json()["data"]["days"]
    check("7d window returns 7 rows (zero-filled)",
          len(days) == 7, [d["date"] for d in days])
    nonempty = [d for d in days if d["workouts"] > 0]
    check("days with sessions keep real reps",
          all(d["reps"] > 0 for d in nonempty) and sum(d["reps"] for d in nonempty) >= 45)
    check("empty days are 0 workouts with form None (no fake form)",
          all(d["workouts"] == 0 and d["reps"] == 0 and d["form_score"] is None for d in days if d["workouts"] == 0))

    print("\n=== RESULT ===")
    if FAILURES:
        print("FAILURES: " + str(len(FAILURES)))
        for item in FAILURES:
            print(" - " + item)
        return 1
    print("ALL VERIFICATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())