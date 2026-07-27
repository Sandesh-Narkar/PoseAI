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

    def test_browser_request_serves_dashboard_html(self):
        response = self.client.get("/", headers={"Accept": "text/html"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.lower().startswith(b"<!doctype html>"))
        self.assertIn(b"main-dashboard", response.data)
        self.assertIn(b"connection-status", response.data)

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
                json={"image": "ZmFrZSBpbWFnZQ=="},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["success"])
            self.assertEqual(payload["data"]["cameraStatus"], "tracking")


if __name__ == "__main__":
    unittest.main()
