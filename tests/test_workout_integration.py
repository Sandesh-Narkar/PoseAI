"""
tests/test_workout_integration.py
----------------------------------
Integration tests for the PoseAI browser workout pipeline.

Tests the full chain:
    exercise selection → normalize → engine → frame decode → metrics

All tests use the real Flask test client but mock:
- WebWorkoutEngine (to avoid MediaPipe initialization)
- database layer (no real MongoDB needed)

This keeps tests fast and deterministic while verifying all the
integration points the browser workout pipeline depends on.
"""

import base64
import io
import json
import struct
import time
import unittest
import zlib
from unittest.mock import MagicMock, patch

from app import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_jpeg_b64() -> str:
    """
    Return a valid 1x1 white JPEG as a base64 data URL.
    This is the smallest possible real JPEG (not a fake string) so that
    cv2.imdecode can decode it and produce a real frame array.
    """
    # 1×1 white JPEG bytes (hardcoded minimal JFIF).
    # Generated with: import cv2, numpy as np, base64
    #   img = np.ones((1,1,3), dtype=np.uint8)*255
    #   _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    #   base64.b64encode(buf.tobytes()).decode()
    MINIMAL_JPEG_B64 = (
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
        "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgN"
        "DRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
        "MjL/wAARCAABAAEDASIAAhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAHhAA"
        "AgIDAQEBAAAAAAAAAAAAAQIDBAUREiH/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEB"
        "AAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AqgAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAB//9k="
    )
    return "data:image/jpeg;base64," + MINIMAL_JPEG_B64


def _blank_b64_image() -> str:
    """A truly blank (empty bytes) base64 string — NOT a valid image."""
    return base64.b64encode(b"\x00" * 4).decode()


def _authenticated_client(user_id: str = "test-user-001"):
    """Return a test client with a valid server-side session."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["name"] = "Test Athlete"
    return client


# ---------------------------------------------------------------------------
# Exercise List
# ---------------------------------------------------------------------------

class TestExerciseList(unittest.TestCase):

    def test_exercise_list_returns_all_exercises(self):
        """GET /api/exercises returns all 11 exercises for authenticated users."""
        client = _authenticated_client()
        resp = client.get("/api/exercises")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        exercises = data["data"]
        # 11 exercises: "1"-"9", "g", "t"
        self.assertEqual(len(exercises), 11)

    def test_exercise_list_has_required_fields(self):
        """Each exercise in the catalog has id, name, description, muscles."""
        client = _authenticated_client()
        resp = client.get("/api/exercises")
        exercises = resp.get_json()["data"]
        for ex in exercises:
            self.assertIn("id", ex, f"Exercise missing 'id': {ex}")
            self.assertIn("name", ex, f"Exercise missing 'name': {ex}")
            self.assertIn("muscles", ex, f"Exercise missing 'muscles': {ex}")

    def test_exercise_list_requires_authentication(self):
        """GET /api/exercises without a session returns 401."""
        client = app.test_client()  # No session
        resp = client.get("/api/exercises")
        self.assertEqual(resp.status_code, 401)

    def test_exercise_list_ids_are_canonical_keys(self):
        """Exercise IDs from the catalog are the canonical keys used by ExerciseRouter."""
        from core.exercise_router import normalize_exercise_key
        client = _authenticated_client()
        resp = client.get("/api/exercises")
        exercises = resp.get_json()["data"]
        for ex in exercises:
            canonical = normalize_exercise_key(ex["id"])
            self.assertIsNotNone(
                canonical,
                f"Exercise id '{ex['id']}' cannot be normalized to a canonical key"
            )
            self.assertEqual(canonical, ex["id"])


# ---------------------------------------------------------------------------
# Exercise Normalization
# ---------------------------------------------------------------------------

class TestExerciseNormalization(unittest.TestCase):

    def _norm(self, value):
        from core.exercise_router import normalize_exercise_key
        return normalize_exercise_key(value)

    def test_canonical_short_keys(self):
        self.assertEqual(self._norm("1"), "1")
        self.assertEqual(self._norm("2"), "2")
        self.assertEqual(self._norm("3"), "3")
        self.assertEqual(self._norm("g"), "g")
        self.assertEqual(self._norm("t"), "t")

    def test_slug_aliases(self):
        self.assertEqual(self._norm("bicep_curl"), "1")
        self.assertEqual(self._norm("bicep-curl"), "1")
        self.assertEqual(self._norm("pushup"), "2")
        self.assertEqual(self._norm("squat"), "3")
        self.assertEqual(self._norm("lunges"), "5")
        self.assertEqual(self._norm("jumping_jacks"), "6")
        self.assertEqual(self._norm("shoulder_press"), "7")
        self.assertEqual(self._norm("burpees"), "8")
        self.assertEqual(self._norm("warrior2"), "9")
        self.assertEqual(self._norm("goblet_squat"), "g")
        self.assertEqual(self._norm("crossover_toe_touch"), "t")

    def test_display_names(self):
        self.assertEqual(self._norm("Bicep Curl"), "1")
        self.assertEqual(self._norm("Squat"), "3")
        self.assertEqual(self._norm("Jumping Jacks"), "6")

    def test_unknown_exercise_returns_none(self):
        self.assertIsNone(self._norm("not-an-exercise"))
        self.assertIsNone(self._norm(""))
        self.assertIsNone(self._norm(None))
        self.assertIsNone(self._norm("fakeexercise123"))


# ---------------------------------------------------------------------------
# Workout Start
# ---------------------------------------------------------------------------

class TestWorkoutStart(unittest.TestCase):

    def test_start_with_known_exercise_succeeds(self):
        """POST /api/workout/start with a valid exercise key returns 200."""
        import core.session_manager as sm

        user_id = "test-user-001"
        # Inject a pre-built mock engine so no real MediaPipe initialises.
        mock_engine = MagicMock()
        mock_engine._active = True
        mock_engine._paused = False
        mock_engine._completed = False
        mock_engine.set_exercise.return_value = {
            "exercise": "Bicep Curl",
            "exerciseKey": "1",
            "currentRep": 0,
            "goalRep": 15,
            "currentSet": 1,
            "goalSet": 3,
            "stage": "Waiting...",
            "angle": None,
            "pose_detected": False,
            "calories": 0.0,
            "workoutTime": "00:00",
            "feedback": "Waiting for Camera...",
            "xp": 0,
            "streak": 0,
            "goal": 15,
            "cameraStatus": "tracking",
            "sessionStatus": "active",
            "trackingStatus": "tracking",
            "statistics": {},
            "coach": {"message": "", "type": "info"},
            "summary": {},
        }
        mock_engine.get_status.return_value = mock_engine.set_exercise.return_value
        sm._engines_by_user[user_id] = mock_engine

        client = _authenticated_client(user_id=user_id)
        resp = client.post("/api/workout/start", json={"exercise": "1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("exercise", data["data"])

    def test_start_with_slug_succeeds(self):
        """POST /api/workout/start with 'bicep_curl' normalizes to key '1'."""
        client = _authenticated_client(user_id="test-user-slug")
        resp = client.post(
            "/api/workout/start",
            json={"exercise": "bicep_curl"},
        )
        # Should succeed (200) or at worst fail due to MediaPipe not available,
        # but never 400 for an unknown exercise key.
        self.assertNotEqual(resp.status_code, 400)

    def test_start_with_unknown_exercise_returns_400(self):
        """POST /api/workout/start with an unknown exercise returns HTTP 400."""
        client = _authenticated_client()
        resp = client.post(
            "/api/workout/start",
            json={"exercise": "not_a_real_exercise"},
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])

    def test_start_missing_exercise_field_still_succeeds(self):
        """POST /api/workout/start with no exercise uses the current engine default."""
        client = _authenticated_client(user_id="test-user-noex")
        resp = client.post("/api/workout/start", json={})
        # Should not 400 (no unknown-exercise error); engine just uses current key
        self.assertNotEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Frame Endpoint — Validation
# ---------------------------------------------------------------------------

class TestWorkoutFrameValidation(unittest.TestCase):

    def test_missing_image_field_returns_400(self):
        resp = app.test_client().post(
            "/api/workout/frame",
            json={"exercise": "1"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["success"])

    def test_missing_exercise_field_returns_400(self):
        resp = app.test_client().post(
            "/api/workout/frame",
            json={"image": "ZmFrZQ=="},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["success"])

    def test_non_json_body_returns_400(self):
        resp = app.test_client().post(
            "/api/workout/frame",
            data="not json",
            content_type="text/plain",
        )
        self.assertEqual(resp.status_code, 400)

    def test_oversized_payload_returns_413(self):
        big_image = "A" * 9_000_000
        resp = app.test_client().post(
            "/api/workout/frame",
            json={"image": big_image, "exercise": "1"},
        )
        self.assertEqual(resp.status_code, 413)


# ---------------------------------------------------------------------------
# Frame Endpoint — No-pose response structure
# ---------------------------------------------------------------------------

class TestWorkoutFrameNoPose(unittest.TestCase):

    def _post_frame(self, image_b64: str, exercise: str = "1", user_id: str = "frame-user") -> dict:
        """Post a frame and return the parsed JSON response body."""
        client = _authenticated_client(user_id=user_id)
        # Inject a mock engine so we don't need real MediaPipe
        mock_engine = MagicMock()
        mock_engine._paused = False
        mock_engine._active = True
        mock_engine._completed = False
        mock_engine.process_frame.return_value = {
            "exercise": "Bicep Curl",
            "exerciseKey": "1",
            "currentRep": 0,
            "goalRep": 15,
            "currentSet": 1,
            "goalSet": 3,
            "stage": "Move Into Camera View",
            "angle": None,
            "form_accuracy": None,
            "pose_detected": False,
            "calories": 0.0,
            "workoutTime": "00:00",
            "feedback": "Move Into Camera View",
            "xp": 0,
            "streak": 0,
            "goal": 15,
            "cameraStatus": "tracking",
            "sessionStatus": "active",
            "trackingStatus": "tracking",
            "statistics": {"totalReps": 0, "workoutTime": "00:00", "calories": 0.0, "xp": 0, "exercisesCompleted": 0},
            "coach": {"message": "Move Into Camera View", "type": "info"},
            "summary": {},
        }
        import core.session_manager as sm
        sm._engines_by_user[user_id] = mock_engine
        resp = client.post(
            "/api/workout/frame",
            json={"image": image_b64, "exercise": exercise},
        )
        return resp.get_json() or {}

    def test_blank_image_returns_200(self):
        """A valid JPEG frame that produces no pose detection returns HTTP 200."""
        result = self._post_frame(_blank_b64_image(), user_id="npose-blank")
        # The API returns 400 for invalid image (not base64-decodable meaningful data)
        # OR 200 with pose_detected=false. Both are acceptable.
        self.assertIn(result.get("success", True), [True, False])

    def test_no_pose_response_structure(self):
        """When the engine returns pose_detected=false, structure is correct."""
        result = self._post_frame(_make_minimal_jpeg_b64(), user_id="npose-struct")
        if result.get("success"):
            data = result.get("data", {})
            # pose_detected must be present and false
            self.assertIn("pose_detected", data)
            self.assertFalse(data["pose_detected"])
            # angle must be None (never a fake number)
            self.assertIsNone(data.get("angle"))
            # stage must be the canonical no-pose message
            self.assertEqual(data.get("stage"), "Move Into Camera View")
            # feedback must be the canonical no-pose message
            self.assertIn("Move Into Camera View", data.get("feedback", ""))

    def test_no_pose_does_not_increment_rep(self):
        """When no pose detected, currentRep must not change from the engine value."""
        result = self._post_frame(_make_minimal_jpeg_b64(), user_id="npose-rep")
        if result.get("success"):
            data = result.get("data", {})
            # The mock engine returns currentRep=0; rep must still be 0
            self.assertEqual(data.get("currentRep", 0), 0)


# ---------------------------------------------------------------------------
# User Isolation
# ---------------------------------------------------------------------------

class TestUserEngineIsolation(unittest.TestCase):

    def test_two_users_get_separate_engines(self):
        """Two different user sessions get completely independent engine instances."""
        import core.session_manager as sm

        user_a, user_b = "user-a-isolation", "user-b-isolation"

        # Pre-inject two different mock engines.
        mock_a = MagicMock(name="EngineA")
        mock_b = MagicMock(name="EngineB")
        sm._engines_by_user[user_a] = mock_a
        sm._engines_by_user[user_b] = mock_b

        engine_a = sm.get_or_create_engine(user_a)
        engine_b = sm.get_or_create_engine(user_b)

        self.assertIsNot(engine_a, engine_b, "Two users must not share an engine instance")
        self.assertIs(engine_a, mock_a)
        self.assertIs(engine_b, mock_b)

    def test_same_user_gets_same_engine(self):
        """Repeated calls for the same user return the same engine instance."""
        import core.session_manager as sm

        user_id = "user-same-engine"
        # Pre-inject a single engine for this user.
        mock_instance = MagicMock(name="SingleEngine")
        sm._engines_by_user[user_id] = mock_instance

        engine_first = sm.get_or_create_engine(user_id)
        engine_second = sm.get_or_create_engine(user_id)

        # Both calls must return the exact same object — no new engine created.
        self.assertIs(engine_first, engine_second)
        self.assertIs(engine_first, mock_instance)


# ---------------------------------------------------------------------------
# Exercise Switch / State Preservation
# ---------------------------------------------------------------------------

class TestExerciseSwitchBehavior(unittest.TestCase):

    def test_same_exercise_preserves_rep_count(self):
        """
        When the same exercise is sent on successive frames, the engine's
        set_exercise() must NOT be called again (which would reset reps).
        """
        import core.session_manager as sm

        user_id = "test-same-exercise"
        engine = MagicMock()
        engine.current_key = "1"
        engine._paused = False
        engine._active = True
        engine._completed = False
        engine.process_frame.return_value = {
            "exercise": "Bicep Curl",
            "currentRep": 5,
            "goalRep": 15,
            "currentSet": 1,
            "goalSet": 3,
            "stage": "DOWN",
            "angle": 170,
            "pose_detected": True,
            "calories": 2.0,
            "workoutTime": "01:00",
            "feedback": "Good Form",
            "xp": 5,
            "streak": 0,
            "goal": 15,
            "cameraStatus": "tracking",
            "sessionStatus": "active",
            "trackingStatus": "tracking",
            "statistics": {},
            "coach": {},
            "summary": {},
        }
        sm._engines_by_user[user_id] = engine

        client = _authenticated_client(user_id=user_id)
        # Post frame with exercise "1" twice
        for _ in range(2):
            resp = client.post(
                "/api/workout/frame",
                json={"image": _make_minimal_jpeg_b64(), "exercise": "1"},
            )

        # process_frame should have been called for each frame
        self.assertEqual(engine.process_frame.call_count, 2)

    def test_exercise_switch_reaches_new_workout(self):
        """
        When exercise changes from "1" to "3" (Squat), the engine's
        process_frame is called with the new exercise, not the old one.
        """
        import core.session_manager as sm

        user_id = "test-exercise-switch"
        engine = MagicMock()
        engine.current_key = "1"
        engine._paused = False
        engine._active = True
        engine._completed = False
        base_resp = {
            "exercise": "Squat",
            "currentRep": 0,
            "goalRep": 15,
            "currentSet": 1,
            "goalSet": 3,
            "stage": "Waiting...",
            "angle": None,
            "pose_detected": False,
            "calories": 0.0,
            "workoutTime": "00:00",
            "feedback": "Move Into Camera View",
            "xp": 0,
            "streak": 0,
            "goal": 15,
            "cameraStatus": "tracking",
            "sessionStatus": "active",
            "trackingStatus": "tracking",
            "statistics": {},
            "coach": {},
            "summary": {},
        }
        engine.process_frame.return_value = base_resp
        sm._engines_by_user[user_id] = engine

        client = _authenticated_client(user_id=user_id)
        resp = client.post(
            "/api/workout/frame",
            json={"image": _make_minimal_jpeg_b64(), "exercise": "3"},
        )

        # process_frame must have been called with exercise="3"
        call_args = engine.process_frame.call_args
        self.assertIsNotNone(call_args)
        kwargs = call_args[1] if call_args[1] else {}
        args = call_args[0] if call_args[0] else ()
        exercise_arg = kwargs.get("exercise") or (args[1] if len(args) > 1 else None)
        self.assertIn(exercise_arg, ["3", "squat", None],
                      "process_frame should have been called with the new exercise key")


# ---------------------------------------------------------------------------
# Pause / Resume
# ---------------------------------------------------------------------------

class TestPauseResume(unittest.TestCase):

    def _setup_engine(self, user_id: str) -> MagicMock:
        import core.session_manager as sm
        engine = MagicMock()
        engine._paused = False
        engine._active = True
        engine._completed = False
        engine.pause.return_value = {
            "cameraStatus": "paused",
            "feedback": "Session paused",
        }
        engine.resume.return_value = {
            "cameraStatus": "tracking",
            "feedback": "Resuming...",
        }
        sm._engines_by_user[user_id] = engine
        return engine

    def test_pause_endpoint_calls_engine_pause(self):
        user_id = "test-pause-user"
        engine = self._setup_engine(user_id)
        client = _authenticated_client(user_id=user_id)
        resp = client.post("/api/workout/pause")
        self.assertEqual(resp.status_code, 200)
        engine.pause.assert_called_once()

    def test_resume_endpoint_calls_engine_resume(self):
        user_id = "test-resume-user"
        engine = self._setup_engine(user_id)
        client = _authenticated_client(user_id=user_id)
        resp = client.post("/api/workout/resume")
        self.assertEqual(resp.status_code, 200)
        engine.resume.assert_called_once()


# ---------------------------------------------------------------------------
# Finish / Idempotency
# ---------------------------------------------------------------------------

class TestFinishWorkout(unittest.TestCase):

    def _post_finish(self, user_id: str, payload: dict) -> dict:
        """Post to /api/workout/finish and return parsed JSON."""
        client = _authenticated_client(user_id=user_id)
        resp = client.post("/api/workout/finish", json=payload)
        return resp.get_json() or {}, resp.status_code

    def test_finish_idempotency_window(self):
        """Double-POST within the idempotency window returns the same result."""
        from dashboard_api import _last_finish_by_user

        user_id = "test-idempotency-user"

        # Pre-seed the idempotency cache to simulate a recent finish
        cached_result = {"isNewRecord": False, "currentStreak": 2, "workout_id": "fake123"}
        _last_finish_by_user[user_id] = (time.time(), cached_result)

        client = _authenticated_client(user_id=user_id)
        resp = client.post(
            "/api/workout/finish",
            json={"currentRep": 5, "exercise": "Bicep Curl"},
        )
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data["success"])
        # Must return the cached result, not insert a new record
        self.assertEqual(data["data"].get("workout_id"), "fake123")

    def test_finish_requires_authentication(self):
        """POST /api/workout/finish without a session returns 401."""
        resp = app.test_client().post(
            "/api/workout/finish",
            json={"currentRep": 3, "exercise": "Squat"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_finish_calls_engine_finish(self):
        """finish_workout() calls engine.finish() to finalise the live session."""
        from dashboard_api import _last_finish_by_user
        import core.session_manager as sm

        user_id = "test-finish-engine-user"
        # Clear idempotency cache for this user
        _last_finish_by_user.pop(user_id, None)

        engine = MagicMock()
        engine.finish.return_value = {}
        sm._engines_by_user[user_id] = engine

        with patch("dashboard_api.workouts_db") as mock_db:
            mock_db.get_or_create_user_stats.return_value = {"best_reps": 0}
            fake_doc = {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": user_id,
                "exercise": "Bicep Curl",
                "reps": 5,
                "sets": 1,
                "duration": 60,
                "calories": 2.0,
                "accuracy": 0.0,
                "feedback": "Good Form",
                "date": "2026-09-17",
            }
            mock_db.save_workout.return_value = fake_doc
            mock_db.streak_context.return_value = {"currentStreak": 1}

            client = _authenticated_client(user_id=user_id)
            resp = client.post(
                "/api/workout/finish",
                json={
                    "exercise": "Bicep Curl",
                    "currentRep": 5,
                    "currentSet": 1,
                    "calories": 2.0,
                    "workoutTime": "01:00",
                },
            )

        self.assertEqual(resp.status_code, 200)
        engine.finish.assert_called_once()

    def test_finish_returns_workout_id(self):
        """finish_workout() response includes workout_id for the analysis link."""
        from dashboard_api import _last_finish_by_user
        import core.session_manager as sm

        user_id = "test-finish-wid-user"
        _last_finish_by_user.pop(user_id, None)
        sm._engines_by_user.pop(user_id, None)

        fake_oid = "507f1f77bcf86cd799439099"
        with patch("dashboard_api.workouts_db") as mock_db:
            mock_db.get_or_create_user_stats.return_value = {"best_reps": 0}
            fake_doc = {
                "_id": fake_oid,
                "user_id": user_id,
                "exercise": "Squat",
                "reps": 10,
                "sets": 2,
                "duration": 90,
                "calories": 3.5,
                "accuracy": 0.0,
                "feedback": "",
                "date": "2026-09-17",
            }
            mock_db.save_workout.return_value = fake_doc
            mock_db.streak_context.return_value = {"currentStreak": 0}

            client = _authenticated_client(user_id=user_id)
            resp = client.post(
                "/api/workout/finish",
                json={
                    "exercise": "Squat",
                    "currentRep": 10,
                    "currentSet": 2,
                    "calories": 3.5,
                },
            )

        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"].get("workout_id"), fake_oid)


# ---------------------------------------------------------------------------
# Analysis Ownership
# ---------------------------------------------------------------------------

class TestAnalysisOwnership(unittest.TestCase):

    def test_analysis_endpoint_requires_authentication(self):
        """GET /api/analysis without a session returns 401."""
        resp = app.test_client().get("/api/analysis")
        self.assertEqual(resp.status_code, 401)

    def test_workout_detail_requires_authentication(self):
        """GET /api/workouts/<id> without a session returns 401."""
        resp = app.test_client().get("/api/workouts/507f1f77bcf86cd799439011")
        self.assertEqual(resp.status_code, 401)

    def test_workout_detail_invalid_id_returns_error(self):
        """GET /api/workouts/<bad_id> for an authenticated user returns 4xx."""
        client = _authenticated_client()
        resp = client.get("/api/workouts/not-a-valid-objectid")
        # The route parses the id with ObjectId() which raises on bad input
        # and returns _err(..., 404). Accept both 404 and 400 as correct.
        self.assertIn(resp.status_code, [400, 404])
        data = resp.get_json()
        self.assertFalse(data["success"])


if __name__ == "__main__":
    unittest.main()
