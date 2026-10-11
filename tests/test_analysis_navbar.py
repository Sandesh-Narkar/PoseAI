"""
Verification script for PoseAI Analysis Page & Global Navbar.
Tests authentication, workout saving, telemetry enrichment, analysis APIs,
previous workout comparison, report generation, and security boundaries.
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ["TESTING"] = "1"
os.environ["MONGO_ALLOW_MOCK"] = "1"

import app as flask_app
import database.workouts as workouts_db
from database.mongo import get_db

class TestAnalysisAndNavbar(unittest.TestCase):
    def test_full_analysis_and_navbar(self):
        import uuid
        uid_hex = uuid.uuid4().hex[:8]
        test_email = f"alex_{uid_hex}@test.com"

        client = flask_app.app.test_client()

        print("=== 1. TEST LOGIN & SESSION ===")
        signup_res = client.post("/auth/signup", json={
            "name": "Alex Coach",
            "email": test_email,
            "password": "Password123!",
        })
        print(f"Signup response: {signup_res.status_code}")

        login_res = client.post("/auth/login", json={
            "email": test_email,
            "password": "Password123!",
        })
        self.assertEqual(login_res.status_code, 200, f"Login failed: {login_res.data}")
        print("User logged in successfully.")

        print("\n=== 2. TEST EMPTY ANALYSIS STATE ===")
        workouts_res = client.get("/api/analysis/workouts")
        self.assertEqual(workouts_res.status_code, 200, f"Get workouts failed: {workouts_res.data}")
        workouts_json = workouts_res.get_json()
        print("Initial workouts list:", workouts_json["data"]["workouts"])
        self.assertEqual(len(workouts_json["data"]["workouts"]), 0, "Expected 0 workouts initially")

        analysis_res = client.get("/api/analysis")
        self.assertEqual(analysis_res.status_code, 200)
        analysis_json = analysis_res.get_json()
        self.assertFalse(analysis_json["data"]["hasData"], "Expected hasData: False on empty history")
        print("Initial empty analysis verified.")

        print("\n=== 3. RECORD FIRST WORKOUT (BICEP CURL) ===")
        workout1_payload = {
            "exercise": "Bicep Curl",
            "currentRep": 12,
            "total_reps": 30,
            "currentSet": 3,
            "completed_sets": 3,
            "target_sets": 3,
            "target_reps": 10,
            "calories": 24.5,
            "duration": 340,
            "accuracy": 88.0,
            "feedback": "Consistent form, good elbow control",
            "rep_history": [
                {"rep": 1, "set": 1, "angle": 150, "form_accuracy": 90, "tempo": 1.8},
                {"rep": 2, "set": 1, "angle": 145, "form_accuracy": 88, "tempo": 1.9},
                {"rep": 3, "set": 2, "angle": 142, "form_accuracy": 86, "tempo": 1.7},
            ],
            "sets_detail": [
                {"set_number": 1, "target_reps": 10, "completed_reps": 10, "accuracy": 89.0, "average_angle": 147, "average_tempo": 1.8, "status": "Completed"},
                {"set_number": 2, "target_reps": 10, "completed_reps": 10, "accuracy": 87.5, "average_angle": 143, "average_tempo": 1.8, "status": "Completed"},
                {"set_number": 3, "target_reps": 10, "completed_reps": 10, "accuracy": 87.5, "average_angle": 141, "average_tempo": 1.7, "status": "Completed"},
            ],
        }
        finish1_res = client.post("/api/workout/finish", json=workout1_payload)
        self.assertEqual(finish1_res.status_code, 200, f"Finish failed: {finish1_res.data}")
        w1_id = finish1_res.get_json()["data"]["workout_id"]
        print(f"Workout 1 saved with ID: {w1_id}")

        print("\n=== 4. RECORD SECOND WORKOUT (SAME EXERCISE — BICEP CURL) ===")
        import dashboard_api
        dashboard_api._last_finish_by_user.clear()
        workout2_payload = {
            "exercise": "Bicep Curl",
            "currentRep": 12,
            "total_reps": 36,
            "currentSet": 3,
            "completed_sets": 3,
            "target_sets": 3,
            "target_reps": 12,
            "calories": 27.0,
            "duration": 402,
            "accuracy": 94.0,
            "feedback": "Excellent elbow stability! Full range of motion",
            "rep_history": [
                {"rep": 1, "set": 1, "angle": 154, "form_accuracy": 95, "tempo": 1.9},
                {"rep": 2, "set": 1, "angle": 152, "form_accuracy": 94, "tempo": 1.8},
                {"rep": 3, "set": 2, "angle": 150, "form_accuracy": 93, "tempo": 1.9},
            ],
            "sets_detail": [
                {"set_number": 1, "target_reps": 12, "completed_reps": 12, "accuracy": 94.5, "average_angle": 153, "average_tempo": 1.9, "status": "Completed"},
                {"set_number": 2, "target_reps": 12, "completed_reps": 12, "accuracy": 93.5, "average_angle": 151, "average_tempo": 1.8, "status": "Completed"},
                {"set_number": 3, "target_reps": 12, "completed_reps": 12, "accuracy": 94.0, "average_angle": 150, "average_tempo": 1.9, "status": "Completed"},
            ],
        }
        finish2_res = client.post("/api/workout/finish", json=workout2_payload)
        self.assertEqual(finish2_res.status_code, 200)
        w2_id = finish2_res.get_json()["data"]["workout_id"]
        print(f"Workout 2 saved with ID: {w2_id}")

        print("\n=== 5. VERIFY WORKOUTS SELECTOR LIST ===")
        list_res = client.get("/api/analysis/workouts")
        self.assertEqual(list_res.status_code, 200)
        list_data = list_res.get_json()["data"]["workouts"]
        print(f"Workouts in selector: {len(list_data)}")
        self.assertEqual(len(list_data), 2, f"Expected 2 workouts, got {len(list_data)}")
        self.assertEqual(list_data[0]["id"], w2_id, "Newest workout should be first")

        print("\n=== 6. VERIFY DETAILED ANALYSIS DATA FOR WORKOUT 2 ===")
        detail_res = client.get(f"/api/analysis/workout/{w2_id}")
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.get_json()["data"]

        self.assertTrue(detail["hasData"])
        self.assertEqual(detail["total_reps"], 36)
        self.assertEqual(detail["completed_sets"], 3)
        self.assertEqual(detail["accuracy"], 94.0)
        self.assertEqual(len(detail["sets_detail"]), 3)
        self.assertTrue(len(detail["strengths"]) > 0)
        self.assertEqual(detail["biomechanics"]["elbow_position"], "Stable")
        self.assertGreaterEqual(detail["form_consistency"]["best"], 90)
        print("AI Coach recommendation:", detail["coach_recommendation"])
        print("Strengths:", detail["strengths"])
        print("Improvements:", detail["improvements"])

        print("\n=== 7. VERIFY PREVIOUS SESSION COMPARISON ===")
        comp_res = client.get(f"/api/analysis/previous/{w2_id}")
        self.assertEqual(comp_res.status_code, 200)
        comp_data = comp_res.get_json()["data"]
        self.assertTrue(comp_data["hasPrevious"], f"Expected hasPrevious: True, got {comp_data}")
        comp = comp_data["comparison"]
        print("Comparison:", comp)
        self.assertEqual(comp["previous"]["id"], w1_id, "Previous session ID should match workout 1")
        self.assertEqual(comp["accuracy_diff"], 6.0, f"Expected +6.0% accuracy diff, got {comp['accuracy_diff']}")
        self.assertEqual(comp["reps_diff"], 6, f"Expected +6 reps diff, got {comp['reps_diff']}")

        print("\n=== 8. VERIFY REPORT DOWNLOAD API ===")
        report_res = client.get(f"/api/analysis/workout/{w2_id}/report")
        self.assertEqual(report_res.status_code, 200)
        report_data = report_res.get_json()["data"]
        self.assertEqual(report_data["report_type"], "PoseAI Workout Analysis Report")
        self.assertNotIn("password", str(report_data).lower(), "Report must NEVER contain passwords")
        self.assertNotIn("secret", str(report_data).lower(), "Report must NEVER contain secrets")
        print("Report generated cleanly without sensitive credentials.")

        print("\n=== 9. VERIFY SECURITY BOUNDARIES & ACCESS CONTROL ===")
        client2 = flask_app.app.test_client()
        client2.post("/auth/signup", json={
            "name": "Eve Sneak",
            "email": f"eve_{uid_hex}@test.com",
            "password": "Password123!",
        })
        client2.post("/auth/login", json={
            "email": f"eve_{uid_hex}@test.com",
            "password": "Password123!",
        })
        eve_res = client2.get(f"/api/analysis/workout/{w2_id}")
        self.assertEqual(eve_res.status_code, 404, f"Security violation! Unauthorized user accessed workout: {eve_res.status_code}")
        print("Security check passed: User cannot access other user's workout.")

        print("\n=== 10. VERIFY GLOBAL NAVBAR ASSETS ===")
        self.assertTrue(os.path.exists("frontend/css/navbar.css"), "frontend/css/navbar.css missing")
        self.assertTrue(os.path.exists("frontend/js/navbar.js"), "frontend/js/navbar.js missing")
        self.assertTrue(os.path.exists("frontend/html/analysis.html"), "frontend/html/analysis.html missing")
        self.assertTrue(os.path.exists("frontend/js/analysis.js"), "frontend/js/analysis.js missing")

        with open("frontend/html/analysis.html", "r", encoding="utf-8") as f:
            analysis_html = f.read()
        self.assertIn("app-header", analysis_html, "Navbar mount point missing in analysis.html")
        self.assertIn("chart.js", analysis_html.lower(), "Chart.js missing in analysis.html")
        self.assertIn("workoutSelector", analysis_html, "Workout selector missing in analysis.html")
        print("All file structures and contracts verified!")

        print("\n>>> ALL POSEAI ANALYSIS & GLOBAL NAVBAR TESTS PASSED! <<<")

if __name__ == "__main__":
    unittest.main()
