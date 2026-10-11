import unittest
from unittest.mock import patch

from app import app


class AppApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["status"], "running")

    def test_status_endpoint_returns_dashboard_state(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIn("exercise", payload["data"])
        self.assertIn("cameraStatus", payload["data"])

    def test_unauthenticated_browser_request_redirects_to_login(self):
        # The new frontend is authenticated: HTML requests without a session
        # must bounce to /login (matches auth suite TEST 13).
        response = self.client.get("/", headers={"Accept": "text/html"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers.get("Location", ""))

    def test_authenticated_browser_request_serves_new_frontend(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = "test-user"
            sess["name"] = "Test User"
        response = self.client.get("/", headers={"Accept": "text/html"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.lower().startswith(b"<!doctype html>"))
        self.assertIn(b"js/shell.js", response.data)
        self.assertIn(b"loadRealDashboard", response.data)

    def test_workout_start_endpoint_accepts_exercise_selection(self):
        with patch("app.get_or_create_workout_engine") as mock_engine:
            mock_engine.return_value = type("Engine", (), {"start": lambda self: None, "set_exercise": lambda self, value: None, "update_dashboard_state": lambda self: None})()
            response = self.client.post(
                "/api/workout/start",
                json={"exercise": "bicep_curl"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["success"])
            self.assertIn("exercise", payload["data"])

    def test_workout_frame_endpoint_accepts_payload(self):
        with patch("app.process_workout_frame") as mock_process:
            mock_process.return_value = {"exercise": "Bicep Curl", "currentRep": 1, "stage": "up"}
            response = self.client.post(
                "/api/workout/frame",
                json={"image": "ZmFrZSBpbWFnZQ==", "exercise": "bicep_curl"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["success"])
            self.assertEqual(payload["data"]["cameraStatus"], "tracking")

    def test_workout_frame_endpoint_rejects_missing_fields(self):
        response = self.client.post("/api/workout/frame", json={"image": "ZmFrZQ=="})
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        response = self.client.post("/api/workout/frame", json={"exercise": "bicep_curl"})
        self.assertEqual(response.status_code, 400)

    def test_exercise_slug_normalizes_to_canonical_key(self):
        from core.exercise_router import normalize_exercise_key

        self.assertEqual(normalize_exercise_key("bicep_curl"), "1")
        self.assertEqual(normalize_exercise_key("Bicep Curl"), "1")
        self.assertEqual(normalize_exercise_key("1"), "1")
        self.assertIsNone(normalize_exercise_key("not-an-exercise"))


if __name__ == "__main__":
    unittest.main()
