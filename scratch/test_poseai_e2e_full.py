"""
End-to-end Verification for PoseAI Full Production Readiness.
Tests every major subsystem through the live Flask test client backed by the real MongoDB Atlas cluster.
"""

import base64
import json
import os
import sys
import time
from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from config import Config
from database import mongo as mongo_db
from database import workouts as workouts_db
from database import market as market_db

def run_e2e():
    print("=" * 70)
    print("POSEAI COMPLETE END-TO-END PRODUCTION VERIFICATION")
    print("=" * 70)

    client = app.test_client()

    # ─────────────────────────────────────────────────────────────────
    # 1. API HEALTH CHECK
    # ─────────────────────────────────────────────────────────────────
    print("\n[1/10] Verifying GET /api/health ...")
    r_health = client.get("/api/health")
    assert r_health.status_code == 200, f"Health check failed: {r_health.status_code}"
    health_data = r_health.get_json()
    print(f"Health Response: {health_data}")
    assert health_data.get("success") is True
    assert health_data.get("status") == "healthy"
    assert health_data.get("database") == "connected"
    print("[OK] Health check passed: Database connected.")

    # ─────────────────────────────────────────────────────────────────
    # 2. USER SIGNUP & ARGON2ID SECURITY
    # ─────────────────────────────────────────────────────────────────
    test_ts = int(time.time())
    user_a_email = f"athlete_a_{test_ts}@example.com"
    user_a_name = f"Athlete Alpha {test_ts}"
    user_a_pass = "ProductionSecure123!"

    print(f"\n[2/10] Verifying Signup for User A ({user_a_email}) ...")
    r_signup = client.post("/auth/signup", json={
        "name": user_a_name,
        "email": user_a_email,
        "password": user_a_pass,
        "confirm_password": user_a_pass,
    })
    assert r_signup.status_code in (200, 201), f"Signup failed: {r_signup.get_data(as_text=True)}"
    signup_json = r_signup.get_json()
    assert signup_json.get("success") is True, f"Signup returned error: {signup_json}"

    user_a_doc = mongo_db.find_user_by_email(user_a_email)
    assert user_a_doc is not None, "User A document was not found in MongoDB!"
    user_a_id = str(user_a_doc["_id"])
    assert user_a_doc.get("password_hash", "").startswith("$argon2id$"), "Password is not hashed with Argon2id!"
    print(f"[OK] User A created in MongoDB with ObjectId {user_a_id} and verified Argon2id hash.")

    # ─────────────────────────────────────────────────────────────────
    # 3. AUTHENTICATED SESSION & PROTECTED ROUTES
    # ─────────────────────────────────────────────────────────────────
    print("\n[3/10] Verifying Login & Protected Route Redirection ...")
    # Unauthenticated check
    unauthed_client = app.test_client()
    r_protected = unauthed_client.get("/api/workout/session")
    assert r_protected.status_code == 200
    assert r_protected.get_json()["data"]["active"] is False

    # Login as User A
    r_login = client.post("/auth/login", json={
        "email": user_a_email,
        "password": user_a_pass,
    })
    assert r_login.status_code == 200, f"Login failed: {r_login.get_data(as_text=True)}"
    login_json = r_login.get_json()
    assert login_json.get("success") is True
    print("[OK] Login successful, session established.")

    r_me = client.get("/api/auth/me")
    assert r_me.status_code == 200
    me_data = r_me.get_json()
    assert me_data.get("authenticated") is True
    assert me_data["user"]["email"] == user_a_email
    print(f"[OK] GET /api/auth/me returned authenticated identity: {me_data['user']['name']}")

    # ─────────────────────────────────────────────────────────────────
    # 4. WORKOUT ENGINE & BROWSER FRAME PROCESSING
    # ─────────────────────────────────────────────────────────────────
    print("\n[4/10] Verifying Workout Engine & Live Browser Frame API ...")
    r_start = client.post("/api/workout/start", json={"exercise": "1"})
    assert r_start.status_code == 200, f"Start workout failed: {r_start.get_data(as_text=True)}"
    print("[OK] Workout started on Exercise 1 (Bicep Curl)")

    # Generate minimal valid JPEG
    MINIMAL_JPEG_B64 = (
        "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
        "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgN"
        "DRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
        "MjL/wAARCAABAAEDASIAAhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAHhAA"
        "AgIDAQEBAAAAAAAAAAAAAQIDBAUREiH/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEB"
        "AAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AqgAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAB//9k="
    )

    r_frame = client.post("/api/workout/frame", json={
        "exercise": "1",
        "image": MINIMAL_JPEG_B64,
    })
    assert r_frame.status_code == 200, f"Frame processing failed: {r_frame.get_data(as_text=True)}"
    frame_json = r_frame.get_json()
    assert frame_json.get("success") is True
    print(f"[OK] Frame processed successfully | Status: {frame_json['data'].get('cameraStatus')} | Exercise: {frame_json['data'].get('exercise')}")

    # ─────────────────────────────────────────────────────────────────
    # 5. FINISH WORKOUT & MONGODB PERSISTENCE
    # ─────────────────────────────────────────────────────────────────
    print("\n[5/10] Verifying Finish Workout & MongoDB Persistence ...")
    finish_payload = {
        "exercise": "Bicep Curl",
        "currentRep": 15,
        "goalRep": 15,
        "currentSet": 3,
        "goalSet": 3,
        "workoutTime": "02:15",
        "calories": 18.5,
        "feedback": "Great form and consistent cadence.",
        "form_history": [{"rep": 1, "accuracy": 92.0}, {"rep": 2, "accuracy": 95.0}],
        "joint_angles": [{"rep": 1, "angle": 142.0}, {"rep": 2, "angle": 145.0}],
    }
    r_finish = client.post("/api/workout/finish", json=finish_payload)
    assert r_finish.status_code == 200, f"Finish workout failed: {r_finish.get_data(as_text=True)}"
    finish_json = r_finish.get_json()
    assert finish_json.get("success") is True
    workout_id = finish_json.get("workout_id") or finish_json["data"].get("workout_id")
    assert workout_id, "No workout_id returned from finish!"
    print(f"[OK] Workout finished and saved to MongoDB with ID: {workout_id}")

    # Verify directly from workouts collection
    saved_workout = workouts_db.get_workout_by_id(user_a_id, workout_id)
    assert saved_workout is not None, "Workout session not found in MongoDB!"
    assert saved_workout["reps"] == 15
    assert saved_workout["user_id"] == user_a_id
    print("[OK] Workout document verified in MongoDB collection.")

    # ─────────────────────────────────────────────────────────────────
    # 6. ANALYSIS, PROGRESS & ACHIEVEMENTS
    # ─────────────────────────────────────────────────────────────────
    print("\n[6/10] Verifying Analysis, Progress, and Achievements ...")
    r_analysis = client.get(f"/api/workouts/{workout_id}")
    assert r_analysis.status_code == 200, f"Analysis failed: {r_analysis.get_data(as_text=True)}"
    analysis_data = r_analysis.get_json().get("data", {})
    assert analysis_data.get("hasData") is True
    assert analysis_data.get("exercise_name") == "Bicep Curl"
    print(f"[OK] Analysis loaded: {analysis_data.get('exercise_name')} | Reps: {analysis_data.get('total_reps')}")

    r_progress = client.get("/api/progress")
    assert r_progress.status_code == 200
    prog_data = r_progress.get_json().get("data", {})
    totals = prog_data.get("totals", {})
    assert totals.get("total_workouts", 0) >= 1
    print(f"[OK] Progress verified: {totals.get('total_workouts')} workout(s) recorded.")

    r_achievements = client.get("/api/achievements")
    assert r_achievements.status_code == 200
    ach_data = r_achievements.get_json().get("data", {})
    print(f"[OK] Achievements verified: {ach_data.get('unlocked')} unlocked / {ach_data.get('total')} total.")

    # ─────────────────────────────────────────────────────────────────
    # 7. PROFILE PERSISTENCE
    # ─────────────────────────────────────────────────────────────────
    print("\n[7/10] Verifying Profile Updates ...")
    r_profile_patch = client.patch("/api/profile", json={
        "age": 28,
        "fitness_goal": "Improve strength",
        "experience_level": "Intermediate",
        "gender": "Prefer not to say",
        "life_stage": "Adult",
        "weight": 75.0,
        "height": 180.0,
    })
    assert r_profile_patch.status_code == 200, f"Profile patch failed: {r_profile_patch.get_data(as_text=True)}"
    updated_user = mongo_db.find_user_by_id(user_a_id)
    assert updated_user.get("age") == 28
    assert updated_user.get("fitness_goal") == "Improve strength"
    print("[OK] Profile changes persisted to MongoDB.")

    # ─────────────────────────────────────────────────────────────────
    # 8. NUTRITION INTELLIGENCE & DAILY TOTALS
    # ─────────────────────────────────────────────────────────────────
    print("\n[8/10] Verifying Nutrition Intelligence ...")
    r_nut_manual = client.post("/api/nutrition/manual", json={
        "food_name": "Oatmeal Bowl",
        "meal_type": "breakfast",
        "portion": {"amount": 150, "unit": "g"},
        "nutrition": {
            "calories_kcal": 250,
            "protein_g": 10.0,
            "carbs_g": 42.0,
            "fat_g": 4.5,
        },
    })
    assert r_nut_manual.status_code in (200, 201), f"Nutrition manual log failed: {r_nut_manual.get_data(as_text=True)}"
    nut_json = r_nut_manual.get_json()
    assert nut_json.get("success") is True

    r_today = client.get("/api/nutrition/today")
    assert r_today.status_code == 200
    today_json = r_today.get_json()
    assert today_json.get("success") is True
    totals = today_json["data"]["totals"]
    assert totals["calories_kcal"] >= 250
    print(f"[OK] Nutrition logged: {totals['calories_kcal']} kcal, {totals['protein_g']}g protein aggregated in MongoDB.")

    # ─────────────────────────────────────────────────────────────────
    # 9. FITNESS MARKET, CART & CHECKOUT
    # ─────────────────────────────────────────────────────────────────
    print("\n[9/10] Verifying Fitness Market, Cart, and Checkout ...")
    r_products = client.get("/api/market/products")
    assert r_products.status_code == 200
    prod_data = r_products.get_json()
    products = prod_data.get("products", [])
    assert len(products) > 0, "No products found in market collection!"
    product = products[0]
    prod_id = str(product["id"])
    print(f"Found product: {product['name']} (ID: {prod_id}) - INR {product['price']}")

    # Add to cart
    r_add_cart = client.post("/api/market/cart", json={
        "product_id": prod_id,
        "quantity": 2,
    })
    assert r_add_cart.status_code in (200, 201), f"Add to cart failed: {r_add_cart.get_data(as_text=True)}"
    cart_payload = r_add_cart.get_json().get("cart", {})
    assert cart_payload.get("item_count") == 2
    print(f"[OK] Added to cart. Items: {cart_payload.get('item_count')} | Subtotal: INR {cart_payload.get('subtotal')}")

    # Checkout & Order creation
    r_order = client.post("/api/market/orders", json={
        "address": {
            "full_name": user_a_name,
            "line1": "123 Tech Boulevard",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560001",
            "phone": "9876543210",
        }
    })
    assert r_order.status_code in (200, 201), f"Order failed: {r_order.get_data(as_text=True)}"
    order_data = r_order.get_json().get("order", {})
    order_id = order_data.get("id") or order_data.get("order_id")
    assert order_id, "No order ID returned!"
    print(f"[OK] Order created and saved to MongoDB: {order_id} | Total: INR {order_data.get('total')}")

    # Verify cart cleared
    r_cart_after = client.get("/api/market/cart")
    cart_after = r_cart_after.get_json().get("cart", {})
    assert cart_after.get("item_count") == 0
    print("[OK] Cart successfully cleared after checkout.")

    # ─────────────────────────────────────────────────────────────────
    # 10. MULTI-USER ISOLATION & LOGOUT
    # ─────────────────────────────────────────────────────────────────
    print("\n[10/10] Verifying Multi-User Isolation & Session Invalidation ...")
    user_b_email = f"athlete_b_{test_ts}@example.com"
    user_b_name = f"Athlete Beta {test_ts}"
    client_b = app.test_client()

    r_signup_b = client_b.post("/auth/signup", json={
        "name": user_b_name,
        "email": user_b_email,
        "password": "PasswordUserB456!",
        "confirm_password": "PasswordUserB456!",
    })
    assert r_signup_b.status_code in (200, 201)

    # User B tries to view User A's workout
    r_b_workout = client_b.get(f"/api/workouts/{workout_id}")
    assert r_b_workout.status_code in (403, 404), f"Security violation! User B could access User A workout: {r_b_workout.status_code}"
    print("[OK] Multi-user isolation verified: User B cannot access User A's workout.")

    # User B checks cart and orders
    r_b_cart = client_b.get("/api/market/cart")
    assert r_b_cart.get_json()["cart"]["item_count"] == 0
    r_b_orders = client_b.get("/api/market/orders")
    assert len(r_b_orders.get_json().get("orders", [])) == 0
    print("[OK] Multi-user isolation verified: User B has separate cart and order history.")

    # Logout User A
    r_logout = client.post("/auth/logout")
    assert r_logout.status_code == 200
    r_after_logout = client.get("/api/auth/me")
    assert r_after_logout.get_json().get("authenticated") is False
    print("[OK] User A logged out and session invalidated.")

    print("\n" + "=" * 70)
    print("ALL 10 VERIFICATION GATES PASSED COMPLETELY!")
    print("=" * 70)

if __name__ == "__main__":
    run_e2e()
