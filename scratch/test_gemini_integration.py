"""
PoseAI Nutrition — Gemini 2.5 Flash Integration Verification Test
"""

import base64
import cv2
import io
import json
import os
import sys

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

import numpy as np
from unittest.mock import MagicMock, patch
from PIL import Image

# 1. Test Pydantic Models
from nutrition.gemini_vision import (
    FoodItem,
    FoodRecognitionResponse,
    DEFAULT_GEMINI_MODEL,
    _prepare_image_part,
    recognize_food_with_gemini,
    is_gemini_available,
)

print("--- Testing Pydantic Schemas ---")
item1 = FoodItem(
    name="Vada Pav",
    portion_estimate="1 piece (approx. 150g)",
    estimated_weight_g=150.0,
    calories=290.0,
    protein_g=6.2,
    carbs_g=36.0,
    fat_g=13.5,
    fiber_g=3.2,
)

response_data = FoodRecognitionResponse(
    is_food=True,
    food_name="Vada Pav with Chutney",
    meal_type_suggestion="snack",
    confidence=0.96,
    portion_description="1 standard serving (approx. 165g)",
    total_weight_g=165.0,
    calories=310.0,
    protein_g=6.8,
    carbs_g=38.5,
    fat_g=14.0,
    fiber_g=3.5,
    sugar_g=2.1,
    sodium_mg=450.0,
    health_classification="occasional",
    health_summary="Fried potato snack with moderate carbohydrates and fats; best enjoyed in moderation.",
    items=[item1],
)

assert response_data.food_name == "Vada Pav with Chutney"
assert response_data.calories == 310.0
assert response_data.fiber_g == 3.5
assert len(response_data.items) == 1
print("Pydantic models validated successfully!")

# 2. Test Image Preparation
print("\n--- Testing Image Part Conversion ---")
# Use textured/non-blurry image
np.random.seed(42)
dummy_img = np.random.randint(50, 200, (300, 300, 3), dtype=np.uint8)
part = _prepare_image_part(dummy_img)
assert part is not None
print("Image part prepared successfully!")

# 3. Test Mock Gemini Call
print("\n--- Testing Gemini Recognition with Mock ---")
mock_client = MagicMock()
mock_genai_response = MagicMock()
mock_genai_response.parsed = response_data
mock_client.models.generate_content.return_value = mock_genai_response

with patch("nutrition.gemini_vision._create_genai_client", return_value=mock_client):
    res = recognize_food_with_gemini(dummy_img)
    assert res is not None
    assert res.food_name == "Vada Pav with Chutney"
    assert res.calories == 310.0
    assert res.items[0].name == "Vada Pav"
    print("Mock Gemini recognition verified!")

# 4. Test analyze_food_image in nutrition.vision
print("\n--- Testing nutrition.vision.analyze_food_image ---")
from nutrition.vision import analyze_food_image

with patch("nutrition.gemini_vision._create_genai_client", return_value=mock_client):
    pipeline_res = analyze_food_image(dummy_img, user_hint="vada pav", default_meal_type="snack")
    assert pipeline_res["success"] is True
    assert pipeline_res["source"] == "gemini_2.5_flash"
    assert pipeline_res["accuracy_level"] == "LEVEL 2 — AI MULTI-MACRO (GEMINI 2.5 FLASH)"
    assert pipeline_res["nutrition"]["calories_kcal"] == 310
    assert pipeline_res["nutrition"]["fiber_g"] == 3.5
    assert pipeline_res["detected_foods"][0]["name"] == "Vada Pav with Chutney"
    assert len(pipeline_res["detected_foods"][0]["items"]) == 1
    print("analyze_food_image with Gemini 2.5 Flash verified successfully!")

# 5. Test Flask Routes
print("\n--- Testing Flask Routes ---")
from app import app

client = app.test_client()
with client.session_transaction() as sess:
    sess["user_id"] = "test_user_gemini"

# Status endpoint
status_res = client.get("/api/nutrition/gemini-status")
assert status_res.status_code == 200
status_json = status_res.get_json()
assert status_json["success"] is True
assert status_json["data"]["model"] == "gemini-2.5-flash"
print(f"Gemini status endpoint verified: {status_json['data']}")

# Scan endpoint with base64 image
_, enc = cv2.imencode(".jpg", dummy_img)
b64_str = "data:image/jpeg;base64," + base64.b64encode(enc).decode("utf-8")

with patch("nutrition.gemini_vision._create_genai_client", return_value=mock_client):
    scan_res = client.post(
        "/api/nutrition/scan",
        json={"image": b64_str, "meal_type": "snack", "hint": "Vada pav"},
    )
    assert scan_res.status_code == 200
    scan_json = scan_res.get_json()
    assert scan_json["success"] is True
    assert scan_json["data"]["source"] == "gemini_2.5_flash"
    assert scan_json["data"]["nutrition"]["fiber_g"] == 3.5
    print("POST /api/nutrition/scan verified successfully with Gemini 2.5 Flash!")

# Test /api/nutrition/confirm endpoint
confirm_payload = {
    "meal_type": "snack",
    "detected_foods": scan_json["data"]["detected_foods"],
    "nutrition": scan_json["data"]["nutrition"],
    "food_quality": scan_json["data"]["food_quality"],
    "source": scan_json["data"]["source"],
    "confidence": scan_json["data"]["confidence"],
}

confirm_res = client.post("/api/nutrition/confirm", json=confirm_payload)
assert confirm_res.status_code == 201, f"Confirm failed: {confirm_res.get_json()}"
confirm_json = confirm_res.get_json()
assert confirm_json["success"] is True
assert "scan_id" in confirm_json
print(f"POST /api/nutrition/confirm verified successfully! Scan ID: {confirm_json['scan_id']}")

print("\nALL GEMINI INTEGRATION TESTS PASSED SUCCESSFULLY!")
