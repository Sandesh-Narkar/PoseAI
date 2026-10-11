"""
PoseAI Nutrition Intelligence System — Comprehensive Test Suite
===============================================================
Verifies:
- Profile-based Mifflin-St Jeor nutrition target calculations
- Image validation & vision food analysis with confidence scoring
- Food database catalog & Indian food search
- Scan confirmation, MongoDB persistence, and daily aggregation
- Workout energy expenditure integration (Net recorded energy = Eaten - Activity)
- Dynamic data-grounded AI Daily Insights
- "You Ate It. Let's Get Active" exercise suggestions linking to PoseAI exercises
- Strict authorization and user isolation
"""

from __future__ import annotations

import io
import json
from datetime import date, datetime, timezone
import pytest
from PIL import Image
from bson import ObjectId

from app import app
from database import mongo as mongo_db
from database.workouts import get_workouts_collection
from nutrition.food_db import get_food_by_id, scale_nutrition, search_foods
from nutrition.repository import (
    delete_scan,
    get_daily_nutrition,
    get_scans_by_date,
    recalculate_daily_nutrition,
    save_scan,
)
from nutrition.service import (
    calculate_user_targets,
    generate_daily_insight,
    suggest_exercise_for_recent_food,
)
from nutrition.vision import (
    analyze_food_image,
    decode_base64_frame,
    validate_and_decode_image,
)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key-nutrition"
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_user():
    """Create a temporary test user in mongo."""
    db = mongo_db.get_db()
    user_id = ObjectId()
    user_doc = {
        "_id": user_id,
        "username": f"arjun_{user_id}",
        "name": "Arjun Sharma",
        "email": f"arjun_{user_id}@example.com",
        "weight": 75.0,
        "height": 178.0,
        "age": 26,
        "gender": "Male",
        "fitness_goal": "Improve strength",
        "weekly_workout_goal": 4,
        "created_at": datetime.now(timezone.utc),
    }
    db["users"].insert_one(user_doc)
    yield user_doc
    db["users"].delete_one({"_id": user_id})
    db["nutrition_scans"].delete_many({"user_id": str(user_id)})
    db["daily_nutrition"].delete_many({"user_id": str(user_id)})
    db["workout_sessions"].delete_many({"user_id": str(user_id)})


# ── TEST 1: NUTRITION TARGETS ──────────────────────────────────────────

def test_targets_unconfigured_profile():
    """Missing critical profile fields must prompt configuration rather than fake numbers."""
    db = mongo_db.get_db()
    uid = ObjectId()
    db["users"].insert_one({
        "_id": uid,
        "username": f"inc_{uid}",
        "name": "Incomplete User",
        "email": f"inc_{uid}@example.com",
        # missing weight, height, age, fitness_goal
    })
    try:
        targets = calculate_user_targets(str(uid))
        assert targets["configured"] is False
        assert "Set your fitness profile" in targets["message"]
        assert targets["calories_kcal"] is None
        assert targets["protein_g"] is None
    finally:
        db["users"].delete_one({"_id": uid})


def test_targets_configured_profile(test_user):
    """Configured profile calculates personalized targets via Mifflin-St Jeor."""
    uid = str(test_user["_id"])
    targets = calculate_user_targets(uid)

    assert targets["configured"] is True
    assert targets["calories_kcal"] > 1800
    assert targets["protein_g"] > 100
    assert targets["carbs_g"] > 150
    assert targets["fat_g"] > 40
    assert targets["fitness_goal"] == "Improve strength"


# ── TEST 2: FOOD DATABASE & INDIAN FOOD SEARCH ─────────────────────────

def test_indian_foods_catalog():
    """Verify common Indian foods are cataloged with authentic macros & quality classifications."""
    indian_keys = ["roti_chapati", "dal_tadka", "paneer_curry", "biryani_chicken", "idli_sambar", "poha", "vada_pav"]
    for k in indian_keys:
        f = get_food_by_id(k)
        assert f is not None, f"Food '{k}' not found in food catalog"
        assert f["per_unit"]["calories_kcal"] > 0
        assert "food_quality" in f
        assert f["food_quality"]["classification"] in {"nutrient_dense", "occasional"}


def test_food_search():
    """Search matches aliases (e.g. chapati -> Roti / Chapati)."""
    results = search_foods("chapati")
    assert len(results) > 0
    assert "Roti" in results[0]["name"]

    dal_results = search_foods("dal")
    assert any("Dal" in r["name"] for r in dal_results)


def test_scale_nutrition():
    """Scaling portion size scales calories and macros accurately."""
    roti = get_food_by_id("roti_chapati")
    single = scale_nutrition(roti, 1.0)
    double = scale_nutrition(roti, 2.0)

    assert double["calories_kcal"] == single["calories_kcal"] * 2
    assert round(double["protein_g"], 1) == round(single["protein_g"] * 2, 1)


# ── TEST 3: IMAGE VALIDATION & VISION ANALYSIS ────────────────────────

def test_image_validation_valid():
    """Decodes valid JPEG image into OpenCV BGR numpy array."""
    img = Image.new("RGB", (200, 200), color=(240, 200, 60))  # yellow-ish
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw_bytes = buf.getvalue()

    bgr, err = validate_and_decode_image(raw_bytes)
    assert err is None
    assert bgr is not None
    assert bgr.shape == (200, 200, 3)


def test_image_validation_invalid_format():
    """Rejects unsupported format (e.g. text/binary random bytes)."""
    bgr, err = validate_and_decode_image(b"not an image binary payload")
    assert bgr is None
    assert "Invalid or corrupted image" in err


def test_food_vision_analysis():
    """Vision analysis returns valid structured result regardless of confidence tier.

    A plain synthetic image (no barcode, no label text, no recognizable food)
    will fall through to Tier 3/4 with low confidence — this is CORRECT behaviour.
    The test verifies the pipeline always returns a structured response with
    all required fields, and that provenance (accuracy_level) is always tracked.
    """
    img = Image.new("RGB", (300, 300), color=(200, 160, 50))  # plain synthetic hue
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    bgr, _ = validate_and_decode_image(buf.getvalue())

    analysis = analyze_food_image(bgr, default_meal_type="lunch")

    # Pipeline must always return a structured result
    assert analysis["success"] is True
    assert isinstance(analysis["confidence"], float)
    assert 0.0 <= analysis["confidence"] <= 1.0

    # All required output keys must be present
    assert "detected_foods" in analysis
    assert "nutrition" in analysis
    assert "calories_kcal" in analysis["nutrition"]
    assert "food_quality" in analysis
    assert "classification" in analysis["food_quality"]

    # Provenance fields must always be present (core accuracy contract)
    assert "accuracy_level" in analysis
    assert analysis["accuracy_level"] in (
        "verified", "database_estimate", "ai_visual_estimate", "unknown",
        # Legacy label strings (pipeline uses these for matched tiers)
        "LEVEL 1 — VERIFIED", "LEVEL 2 — DATABASE ESTIMATE",
        "LEVEL 3 — AI VISUAL ESTIMATE", "LEVEL 4 — UNKNOWN",
    )
    assert "source_type" in analysis


# ── TEST 4: LOGGING SCANS & DAILY AGGREGATION ──────────────────────────

def test_save_and_recalculate_daily(test_user):
    """Logging multiple scans aggregates totals and maintains consistency."""
    uid = str(test_user["_id"])
    today_str = date.today().isoformat()

    # Log Meal 1: Breakfast Roti + Boiled Eggs
    scan1 = {
        "date": today_str,
        "meal_type": "breakfast",
        "detected_foods": [{"id": "roti_chapati", "name": "Roti", "quantity": "2 pieces"}],
        "nutrition": {"calories_kcal": 208, "protein_g": 6.8, "carbs_g": 44.0, "fat_g": 1.6, "fiber_g": 5.6, "sugar_g": 0.6, "sodium_mg": 190},
        "food_quality": {"classification": "nutrient_dense"},
    }
    scan1_id = save_scan(uid, scan1)
    assert scan1_id is not None

    # Log Meal 2: Lunch Chicken Biryani
    scan2 = {
        "date": today_str,
        "meal_type": "lunch",
        "detected_foods": [{"id": "biryani_chicken", "name": "Chicken Biryani", "quantity": "1 plate"}],
        "nutrition": {"calories_kcal": 560, "protein_g": 32.0, "carbs_g": 66.0, "fat_g": 18.5, "fiber_g": 3.2, "sugar_g": 2.4, "sodium_mg": 780},
        "food_quality": {"classification": "nutrient_dense"},
    }
    save_scan(uid, scan2)

    # Verify daily totals
    daily = get_daily_nutrition(uid, today_str)
    assert daily["totals"]["calories_kcal"] == 208 + 560
    assert daily["totals"]["protein_g"] == round(6.8 + 32.0, 1)
    assert daily["meal_count"] == 2
    assert daily["scan_count"] == 2


def test_delete_scan_recalculates(test_user):
    """Deleting a scan immediately recalculates daily nutrition idempotently."""
    uid = str(test_user["_id"])
    today_str = date.today().isoformat()

    scan_id = save_scan(uid, {
        "date": today_str,
        "meal_type": "snack",
        "detected_foods": [{"id": "vada_pav", "name": "Vada Pav", "quantity": "1 piece"}],
        "nutrition": {"calories_kcal": 290, "protein_g": 6.2, "carbs_g": 42.0, "fat_g": 11.0, "fiber_g": 2.8, "sugar_g": 3.0, "sodium_mg": 460},
        "food_quality": {"classification": "occasional"},
    })

    daily_before = get_daily_nutrition(uid, today_str)
    assert daily_before["totals"]["calories_kcal"] == 290

    # Delete scan
    deleted = delete_scan(uid, scan_id)
    assert deleted is True

    daily_after = get_daily_nutrition(uid, today_str)
    assert daily_after["totals"]["calories_kcal"] == 0
    assert daily_after["scan_count"] == 0


# ── TEST 5: WORKOUT ACTIVITY & ENERGY BALANCE INTEGRATION ─────────────

def test_workout_energy_integration(test_user):
    """Real workout sessions in MongoDB update Nutrition activity and Net recorded energy."""
    uid = str(test_user["_id"])
    today_str = date.today().isoformat()

    # Log food: 1,640 kcal
    save_scan(uid, {
        "date": today_str,
        "meal_type": "lunch",
        "detected_foods": [{"id": "thali", "name": "Thali"}],
        "nutrition": {"calories_kcal": 1640, "protein_g": 78.0, "carbs_g": 210.0, "fat_g": 54.0, "fiber_g": 18.0, "sugar_g": 48.0, "sodium_mg": 1400},
        "food_quality": {"classification": "nutrient_dense"},
    })

    # Insert real workout sessions in workout_sessions collection
    workout_coll = get_workouts_collection()
    workout_coll.insert_one({
        "user_id": uid,
        "date": today_str,
        "exercise": "squats",
        "reps": 45,
        "sets": 3,
        "duration": 900,
        "calories": 220.0,
        "accuracy": 92.0,
        "created_at": datetime.now(timezone.utc),
    })
    workout_coll.insert_one({
        "user_id": uid,
        "date": today_str,
        "exercise": "pushups",
        "reps": 30,
        "sets": 3,
        "duration": 600,
        "calories": 200.0,
        "accuracy": 89.0,
        "created_at": datetime.now(timezone.utc),
    })

    # Recalculate daily nutrition
    daily = recalculate_daily_nutrition(uid, today_str)
    assert daily["activity"]["estimated_workout_kcal"] == 420
    assert daily["activity"]["workout_count"] == 2

    # Check Net Recorded Energy
    assert daily["net_recorded_energy_kcal"] == 1640 - 420  # 1220 kcal


# ── TEST 6: DYNAMIC AI DAILY INSIGHTS ─────────────

def test_ai_daily_insight_synthesis():
    """Generates data-grounded insights synthesizing food intake and workout data."""
    totals = {"calories_kcal": 1640, "protein_g": 78.0, "carbs_g": 210.0, "fat_g": 54.0}
    targets = {"calories_kcal": 2200, "protein_g": 120, "carbs_g": 275, "fat_g": 70}
    activity = {"estimated_workout_kcal": 420, "workout_count": 2}
    today_workouts = [{"exercise": "squats"}, {"exercise": "pushups"}]

    insight = generate_daily_insight(totals, targets, activity, today_workouts)
    assert "78" in insight["summary"]
    assert "120" in insight["summary"]
    assert "420" in insight["summary"] or "workout" in insight["summary"].lower()
    assert len(insight["observations"]) > 0
    assert len(insight["recommendations"]) > 0


# ── TEST 7: 'YOU ATE IT. LET'S GET ACTIVE' ────────

def test_activity_suggestion():
    """Suggests an existing PoseAI exercise with direct workout URL."""
    scans = [
        {
            "detected_foods": [{"name": "Chocolate Bar"}],
            "nutrition": {"calories_kcal": 235},
        }
    ]
    act = suggest_exercise_for_recent_food(scans, "dummy_user")
    assert act["estimated_kcal"] == 235
    assert "Chocolate Bar" in act["headline"]
    assert act["suggested_exercise"]["start_url"].startswith("/workout?exercise=")


# ── TEST 8: REST API ENDPOINTS & AUTHORIZATION ────────────────────────

def test_unauthenticated_api_access(client):
    """Endpoints reject requests without an authenticated session."""
    resp = client.get("/api/nutrition/today")
    assert resp.status_code == 401

    resp = client.post("/api/nutrition/scan")
    assert resp.status_code == 401

    resp = client.post("/api/nutrition/confirm", json={"meal_type": "lunch"})
    assert resp.status_code == 401


def test_authenticated_api_flow(client, test_user):
    """Test authenticated scan, confirm, today summary, and trends flow."""
    with client.session_transaction() as sess:
        sess["user_id"] = str(test_user["_id"])

    # 1. GET /api/nutrition/today
    res_today = client.get("/api/nutrition/today")
    assert res_today.status_code == 200
    today_json = res_today.get_json()
    assert today_json["success"] is True
    assert "energy_balance" in today_json["data"]

    # 2. POST /api/nutrition/confirm
    res_confirm = client.post("/api/nutrition/confirm", json={
        "meal_type": "lunch",
        "detected_foods": [{"id": "roti_chapati", "name": "Roti / Chapati", "quantity": "2 pieces"}],
        "nutrition": {"calories_kcal": 208, "protein_g": 6.8, "carbs_g": 44.0, "fat_g": 1.6, "fiber_g": 5.6, "sugar_g": 0.6, "sodium_mg": 190},
        "food_quality": {"classification": "nutrient_dense"},
    })
    assert res_confirm.status_code == 201
    scan_id = res_confirm.get_json()["scan_id"]

    # 3. GET /api/nutrition/today (verify updated)
    res_today2 = client.get("/api/nutrition/today")
    assert res_today2.get_json()["data"]["totals"]["calories_kcal"] == 208

    # 4. GET /api/nutrition/trends
    res_trends = client.get("/api/nutrition/trends?days=7")
    assert res_trends.status_code == 200
    trends_json = res_trends.get_json()
    assert len(trends_json["data"]["history"]) == 7

    # 5. DELETE /api/nutrition/scan/<scan_id>
    res_del = client.delete(f"/api/nutrition/scan/{scan_id}")
    assert res_del.status_code == 200


# ── NEW TESTS: NutritionValidator ──────────────────────────────────────────

def test_nutrition_validator_valid():
    """Valid chips nutrition passes validator without errors."""
    from nutrition.validator import validate_nutrition, check_calorie_consistency

    nutrition = {
        "calories_kcal": 150,
        "protein_g": 2.0,
        "carbs_g": 15.0,
        "fat_g": 10.0,
        "fiber_g": 1.0,
        "sugar_g": 0.5,
        "sodium_mg": 170,
    }
    result = validate_nutrition(nutrition)
    assert result["valid"] is True
    assert len(result["errors"]) == 0

    # Calorie consistency: 2*4 + 15*4 + 10*9 = 8 + 60 + 90 = 158 ≈ 150 (within 25%)
    cc = check_calorie_consistency(nutrition)
    assert cc["consistent"] is True


def test_nutrition_validator_impossible():
    """Impossible values (protein > 50g AND calories < 50) are rejected."""
    from nutrition.validator import validate_nutrition

    nutrition = {
        "calories_kcal": 20,
        "protein_g": 500.0,   # impossible: 500g protein alone = 2000 kcal
        "carbs_g": 0.0,
        "fat_g": 0.0,
    }
    result = validate_nutrition(nutrition)
    assert result["valid"] is False
    assert len(result["errors"]) > 0
    # Should flag protein out of range AND impossible combination
    error_text = " ".join(result["errors"]).lower()
    assert "protein" in error_text or "impossible" in error_text


def test_nutrition_validator_calorie_inconsistency():
    """Severe calorie inconsistency triggers a warning."""
    from nutrition.validator import validate_nutrition

    # Declared 500 kcal but macros only compute ~100 kcal
    nutrition = {
        "calories_kcal": 500,
        "protein_g": 5.0,    # 20 kcal
        "carbs_g": 10.0,     # 40 kcal
        "fat_g": 5.0,        # 45 kcal  → total ~105 kcal, delta ~79%
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 100,
    }
    result = validate_nutrition(nutrition)
    # Should be valid (no hard errors) but with warning
    assert len(result["warnings"]) > 0
    warning_text = " ".join(result["warnings"]).lower()
    assert "inconsist" in warning_text or "calorie" in warning_text


def test_nutrition_validator_sanitize():
    """Sanitize replaces None values with 0 and clamps out-of-range values."""
    from nutrition.validator import sanitize_nutrition

    dirty = {
        "calories_kcal": None,
        "protein_g": -5.0,      # below 0 → clamped to 0
        "carbs_g": 300.0,       # above 200 → clamped to 200
        "fat_g": 10.0,
        "fiber_g": None,
        "sugar_g": 5.0,
        "sodium_mg": None,
    }
    clean = sanitize_nutrition(dirty)
    assert clean["calories_kcal"] == 0
    assert clean["protein_g"] == 0.0
    assert clean["carbs_g"] == 200.0   # clamped to max
    assert clean["fat_g"] == 10.0
    assert clean["fiber_g"] == 0.0
    assert clean["sodium_mg"] == 0


def test_product_lookup_offline_seed():
    """Offline seed returns correct verified product for known barcode."""
    from nutrition.packaged_db import get_packaged_by_barcode, search_packaged_by_text

    # Barcode lookup
    product = get_packaged_by_barcode("8901491101837")  # Lay's Classic Salted
    assert product is not None
    brand_lower = product["brand"].lower()
    assert "lay" in brand_lower  # matches "lay's"
    assert product["nutrition_per_serving"]["protein_g"] < 5.0   # NOT "high protein"
    assert product["nutrition_per_serving"]["calories_kcal"] > 100

    # Text search
    results = search_packaged_by_text("lays chips salted")
    assert len(results) > 0
    assert "lay" in results[0]["brand"].lower()

    # Ensure Lay's protein is realistically low (not hallucinated)
    assert product["nutrition_per_serving"]["protein_g"] <= 3.0



def test_multi_image_session_lifecycle():
    """Session store create → add_image → session_summary → close lifecycle."""
    from nutrition import session_store as ss
    import numpy as np

    user_id = "test_session_user_999"
    session_id = ss.create_session(user_id)

    # Session must exist and belong to user
    sess = ss.get_session(session_id, user_id)
    assert sess is not None
    assert sess["user_id"] == user_id

    # Wrong user cannot access session
    assert ss.get_session(session_id, "other_user") is None

    # Add a dummy front image
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    result = ss.add_image(session_id, user_id, "front", dummy_img)
    assert result is True

    # Reject invalid image_type
    result_bad = ss.add_image(session_id, user_id, "unknown_type", dummy_img)
    assert result_bad is False

    # Set a partial result
    ss.set_partial_result(session_id, user_id, "barcode_detected", "8901491101837")
    sess2 = ss.get_session(session_id, user_id)
    assert sess2["partial_results"]["barcode_detected"] == "8901491101837"

    # Summary
    summary = ss.session_summary(sess2)
    assert summary["session_id"] == session_id
    assert summary["images_uploaded"]["front"] is True
    assert summary["images_uploaded"]["barcode"] is False

    # Close
    ss.close_session(session_id)
    assert ss.get_session(session_id, user_id) is None


# ── MANUAL NUTRITION ENTRY & CUSTOM FOOD LIBRARY ─────────────────────

def _login(client, user_id: str) -> None:
    """Attach an authenticated user to the test client session."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_manual_entry_requires_auth(client):
    """Manual entry must be scoped to an authenticated user."""
    res = client.post("/api/nutrition/manual", json={
        "food_name": "Rice",
        "nutrition": {"calories_kcal": 200},
    })
    assert res.status_code == 401


def test_manual_entry_endpoint(client, test_user):
    """Manual entry saves validated user values and feeds daily aggregation."""
    uid = str(test_user["_id"])
    _login(client, uid)

    payload = {
        "food_name": "Home-cooked rice",
        "meal_type": "lunch",
        "nutrition": {
            "calories_kcal": 200, "protein_g": 4, "carbs_g": 42,
            "fat_g": 1, "fiber_g": 1, "sugar_g": 0.5, "sodium_mg": 5,
        },
        "portion": {"amount": 150, "unit": "g"},
    }

    res = client.post("/api/nutrition/manual", json=payload)
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["success"] is True
    assert body["scan_id"]

    # Daily totals must include the manually entered meal
    today = client.get("/api/nutrition/today").get_json()["data"]
    assert today["totals"]["calories_kcal"] == 200
    assert today["totals"]["protein_g"] == 4.0

    # Stored with honest provenance — never presented as machine-verified
    day = client.get(f"/api/nutrition/day/{date.today().isoformat()}").get_json()["data"]
    scan = day["scans"][0]
    assert scan["accuracy_level"] == "user_entered"
    assert scan["source_type"] == "user_input"
    assert scan["detected_foods"][0]["name"] == "Home-cooked rice"

    # Missing food_name -> 400
    assert client.post(
        "/api/nutrition/manual", json={"nutrition": {"calories_kcal": 10}}
    ).status_code == 400

    # Missing nutrition -> 400
    assert client.post(
        "/api/nutrition/manual", json={"food_name": "Mystery"}
    ).status_code == 400

    # Impossible values -> 422 and NOT persisted
    bad = {
        "food_name": "Fabricated feast",
        "meal_type": "lunch",
        "nutrition": {"calories_kcal": 99999, "protein_g": 4,
                      "carbs_g": 42, "fat_g": 1},
        "portion": {"amount": 150, "unit": "g"},
    }
    bad_res = client.post("/api/nutrition/manual", json=bad)
    assert bad_res.status_code == 422
    assert bad_res.get_json()["validation_errors"]

    after = client.get("/api/nutrition/today").get_json()["data"]
    assert after["totals"]["calories_kcal"] == 200   # unchanged
    assert after["scan_count"] == 1
def test_custom_food_library_roundtrip(client, test_user):
    """Saved custom foods can be created, listed, updated in place, and deleted."""
    uid = str(test_user["_id"])
    _login(client, uid)

    try:
        res = client.post("/api/nutrition/manual", json={
            "food_name": "Amma's Sambar",
            "meal_type": "dinner",
            "nutrition": {"calories_kcal": 120, "protein_g": 5, "carbs_g": 14,
                          "fat_g": 4, "fiber_g": 3, "sugar_g": 2, "sodium_mg": 380},
            "portion": {"amount": 200, "unit": "ml"},
            "save_to_library": True,
        })
        assert res.status_code == 201, res.get_json()
        assert res.get_json().get("custom_food_id")

        foods = client.get("/api/nutrition/my-foods").get_json()["data"]
        assert len(foods) == 1
        assert foods[0]["name"] == "Amma's Sambar"
        assert foods[0]["portion"]["unit"] == "ml"

        # Saving the same name again updates the template, no duplicate row
        assert client.post("/api/nutrition/manual", json={
            "food_name": "Amma's Sambar",
            "meal_type": "dinner",
            "nutrition": {"calories_kcal": 130, "protein_g": 5,
                          "carbs_g": 15, "fat_g": 4},
            "portion": {"amount": 200, "unit": "ml"},
            "save_to_library": True,
        }).status_code == 201

        foods2 = client.get("/api/nutrition/my-foods").get_json()["data"]
        assert len(foods2) == 1
        assert foods2[0]["nutrition"]["calories_kcal"] == 130

        # Delete removes it
        fid = foods2[0]["id"]
        assert client.delete(f"/api/nutrition/my-foods/{fid}").status_code == 200
        assert client.get("/api/nutrition/my-foods").get_json()["data"] == []

        # Unknown id -> 404
        assert client.delete(f"/api/nutrition/my-foods/{fid}").status_code == 404
    finally:
        mongo_db.get_db()["custom_foods"].delete_many({"user_id": uid})


# ── CROSS-SOURCE CONFLICT DETECTION ───────────────────────────────────

def test_conflict_detection_high_severity():
    """Large disagreements are flagged high; close readings are not flagged."""
    from nutrition.validator import compare_nutrition_sources

    # Per the plan's example: 130 vs 150 kcal -> 15.4% delta -> "low"
    low = compare_nutrition_sources(
        {"calories_kcal": 130}, {"calories_kcal": 150},
        label_a="ocr", label_b="database",
    )
    assert low["has_conflict"] is True
    assert low["severity"] == "low"
    assert "calories_kcal" in low["fields"]
    assert low["delta_pct"]["calories_kcal"] == 15.4
    assert low["higher_source"] == "database"

    # A big disagreement -> "high"
    high = compare_nutrition_sources(
        {"calories_kcal": 100, "protein_g": 2.0},
        {"calories_kcal": 145, "protein_g": 9.0},
        label_a="ocr", label_b="database",
    )
    assert high["has_conflict"] is True
    assert high["severity"] == "high"
    assert set(high["fields"]) == {"calories_kcal", "protein_g"}

    # Sources in agreement -> no conflict
    agree = compare_nutrition_sources(
        {"calories_kcal": 200, "protein_g": 4.0, "carbs_g": 42.0, "fat_g": 1.0},
        {"calories_kcal": 202, "protein_g": 4.1, "carbs_g": 42.5, "fat_g": 1.0},
    )
    assert agree["has_conflict"] is False
    assert agree["severity"] == "none"

    # Missing input must not raise
    assert compare_nutrition_sources(None, {"calories_kcal": 100})["has_conflict"] is False
