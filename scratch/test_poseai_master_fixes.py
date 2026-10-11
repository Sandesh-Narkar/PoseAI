"""
PoseAI Master Verification Script
Tests all requirements from the MASTER PROMPT:
1. Real user greeting & session integration
2. Workout Analysis: form accuracy trend, adaptive joint angle, set details, report download
3. Progress: real calendar dates (YYYY-MM-DD), per-exercise breakdown per day, date ranges
4. Nutrition: Chicken Curry search & confirmation, real MongoDB storage, daily totals update, macro trend
5. Cart & Checkout: item structure, dynamic user address, order placement
6. Complete emoji elimination across frontend HTML files
"""

import os
import re
import sys
import unittest
from datetime import date, datetime

os.environ["TESTING"] = "1"
os.environ["MONGO_ALLOW_MOCK"] = "1"

# Add root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from database import workouts as workouts_db
from nutrition.food_db import get_food_by_id, search_foods


class TestPoseAIMasterFixes(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

        import uuid
        uid = uuid.uuid4().hex
        self.username = f"master_user_{uid}"
        self.email = f"{self.username}@poseai.test"
        self.password = "Password123!"
        self.full_name = "Satyam Sharma"

        # Register
        reg_resp = self.client.post("/auth/signup", json={
            "name": self.full_name,
            "email": self.email,
            "password": self.password,
        })
        self.assertEqual(reg_resp.status_code, 201)

    def test_01_user_identity_and_dashboard(self):
        """Verify session identity returns real user name, not hardcoded."""
        me_resp = self.client.get("/api/auth/me")
        self.assertEqual(me_resp.status_code, 200)
        user_data = me_resp.get_json().get("user", {})
        self.assertIn(user_data.get("full_name") or user_data.get("name") or user_data.get("username"), [self.full_name, self.username])

    def test_02_workout_analysis_and_report_download(self):
        """Verify workout analysis returns real series and report download contains all required fields."""
        # 1. Save a real workout session for bicep_curl
        finish_resp = self.client.post("/api/workout/finish", json={
            "exercise": "bicep_curl",
            "exercise_name": "Bicep Curl",
            "total_reps": 24,
            "completed_sets": 2,
            "target_sets": 2,
            "form_accuracy": 92.5,
            "duration": 180,
            "calories": 45.0,
            "angles": [65, 85, 115, 145, 160, 140, 110, 80, 60],
            "form_history": [88, 90, 92, 94, 91, 95],
            "sets_detail": [
                {"set_number": 1, "reps": 12, "completed_reps": 12, "target_reps": 12, "accuracy": 91.0, "average_angle": 110.0, "average_tempo": 2.4, "status": "Completed"},
                {"set_number": 2, "reps": 12, "completed_reps": 12, "target_reps": 12, "accuracy": 94.0, "average_angle": 112.0, "average_tempo": 2.3, "status": "Completed"}
            ]
        })
        self.assertEqual(finish_resp.status_code, 200)
        workout_id = finish_resp.get_json().get("data", {}).get("workout_id")
        self.assertTrue(workout_id)

        # 2. Query /api/analysis/workout/<id>
        analysis_resp = self.client.get(f"/api/analysis/workout/{workout_id}")
        self.assertEqual(analysis_resp.status_code, 200)
        adata = analysis_resp.get_json().get("data", {})
        self.assertEqual(adata.get("total_reps"), 24)
        self.assertEqual(len(adata.get("sets_detail", [])), 2)
        self.assertTrue(adata.get("angle_metrics"))

        # 3. Query report download endpoint
        report_resp = self.client.get(f"/api/analysis/workout/{workout_id}/report")
        self.assertEqual(report_resp.status_code, 200)
        rdata = report_resp.get_json().get("data", {})
        self.assertIn("workout", rdata)
        self.assertIn("biomechanics", rdata)
        self.assertIn("joint_angle_metrics", rdata)
        self.assertIn("ai_coach_recommendation", rdata)
        self.assertIn("set_by_set_performance", rdata)

    def test_03_progress_real_dates_and_exercise_breakdown(self):
        """Verify progress returns actual calendar dates (YYYY-MM-DD), not Mon/Tue."""
        prog_resp = self.client.get("/api/progress?range=7d")
        self.assertEqual(prog_resp.status_code, 200)
        pdata = prog_resp.get_json().get("data", {})
        days = pdata.get("days", [])
        self.assertTrue(len(days) > 0)
        for d in days:
            # Check date format is YYYY-MM-DD
            self.assertRegex(d["date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertNotIn(d["date"].lower(), ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
            self.assertIn("exercises", d)

    def test_04_nutrition_candidate_and_confirmation_flow(self):
        """Verify Chicken Curry search, selection, and confirmation creates real record and updates totals."""
        # 1. Search for Chicken Curry
        search_resp = self.client.get("/api/nutrition/search?q=Chicken%20Curry")
        self.assertEqual(search_resp.status_code, 200)
        search_data = search_resp.get_json().get("data", [])
        self.assertTrue(len(search_data) > 0)
        found = any("chicken" in (f.get("name", "").lower() + f.get("id", "").lower()) for f in search_data)
        self.assertTrue(found, "Expected chicken curry in search results")

        # 2. Also search by exact ID
        id_resp = self.client.get("/api/nutrition/search?q=chicken_curry")
        self.assertEqual(id_resp.status_code, 200)
        id_data = id_resp.get_json().get("data", [])
        self.assertTrue(len(id_data) > 0)
        self.assertEqual(id_data[0]["id"], "chicken_curry")

        # 3. Confirm food log (Add to Today)
        curry_food = id_data[0]
        confirm_resp = self.client.post("/api/nutrition/confirm", json={
            "meal_type": "lunch",
            "canonical_id": curry_food["id"],
            "food_name": curry_food["name"],
            "detected_foods": [{
                "id": curry_food["id"],
                "name": curry_food["name"],
                "quantity": "1 bowl",
                "serving_qty": 1.0,
                "serving_unit": curry_food.get("serving_unit", "bowl"),
                "confidence": 0.95,
            }],
            "nutrition": curry_food["per_unit"],
            "source": "curated_catalog",
            "confidence": 0.95,
        })
        self.assertEqual(confirm_resp.status_code, 201)
        scan_id = confirm_resp.get_json().get("scan_id")
        self.assertTrue(scan_id)

        # 4. Check today's summary reflects confirmed meal
        today_resp = self.client.get("/api/nutrition/today")
        self.assertEqual(today_resp.status_code, 200)
        tdata = today_resp.get_json().get("data", {})
        totals = tdata.get("totals", {})
        self.assertGreaterEqual(totals.get("calories_kcal", 0), 300)
        self.assertGreaterEqual(totals.get("protein_g", 0), 30)

        # 5. Check /api/nutrition/trends?days=7
        trends_resp = self.client.get("/api/nutrition/trends?days=7")
        self.assertEqual(trends_resp.status_code, 200)
        trdata = trends_resp.get_json().get("data", {})
        history = trdata.get("history", [])
        self.assertTrue(len(history) > 0)
        for h in history:
            self.assertRegex(h["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_05_cart_and_order_placement(self):
        """Verify cart addition and real order placement through backend."""
        # 0. Seed catalog if empty
        from market.seed import seed_if_empty
        seed_if_empty(force_reset=True)

        # Get real product from catalog
        products_resp = self.client.get("/api/market/products")
        self.assertEqual(products_resp.status_code, 200)
        pjson = products_resp.get_json()
        products = pjson.get("products") or pjson.get("data", {}).get("products", [])
        self.assertTrue(len(products) > 0)
        product_id = products[0]["id"]

        # 1. Add item to cart
        add_resp = self.client.post("/api/market/cart", json={
            "product_id": product_id,
            "quantity": 1
        })
        self.assertIn(add_resp.status_code, (200, 201))
        cart = add_resp.get_json().get("cart") or add_resp.get_json().get("data", {}).get("cart", {})
        self.assertGreaterEqual(len(cart.get("items", [])), 1)

        # 2. Place order with validated address
        order_resp = self.client.post("/api/market/orders", json={
            "shipping_address": {
                "full_name": "Satyam Sharma",
                "phone": "9876543210",
                "pincode": "560038",
                "line1": "100 Feet Road, Indiranagar",
                "city": "Bengaluru",
                "state": "Karnataka"
            }
        })
        self.assertEqual(order_resp.status_code, 201)
        ojson = order_resp.get_json()
        order = ojson.get("order") or ojson.get("data", {}).get("order", {})
        self.assertTrue(order.get("order_number"))
        self.assertEqual(order.get("status", "").lower(), "pending")

        # 3. Verify cart is cleared after order
        cjson = self.client.get("/api/market/cart").get_json()
        cart_after = cjson.get("cart") or cjson.get("data", {}).get("cart", {})
        self.assertEqual(len(cart_after.get("items", [])), 0)

    def test_07_market_multi_category_filtering(self):
        """Verify selecting multiple categories (Protein + Supplements + Performance) works without error."""
        # Query with comma-separated categories: protein,supplements,performance
        resp = self.client.get("/api/market/products?category=protein,supplements,performance&limit=50")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        items = data.get("items") or data.get("products") or []
        self.assertGreaterEqual(data.get("total", 0), 24, "Should find products across multiple selected categories")
        self.assertGreaterEqual(len(items), 24)

        # Also test with separate category params
        resp2 = self.client.get("/api/market/products?category=protein&category=supplements&limit=50")
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertTrue(data2.get("success"))
        items2 = data2.get("items") or data2.get("products") or []
        self.assertGreaterEqual(len(items2), 20)

    def test_06_zero_emojis_in_frontend_html(self):
        """Verify ZERO UI emojis exist across all frontend HTML files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]")
        frontend_html_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "html")
        for filename in os.listdir(frontend_html_dir):
            if filename.endswith(".html"):
                filepath = os.path.join(frontend_html_dir, filename)
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                emojis = emoji_pattern.findall(content)
                self.assertEqual(len(emojis), 0, f"Found {len(emojis)} emojis in {filename}: {emojis}")


if __name__ == "__main__":
    unittest.main()
