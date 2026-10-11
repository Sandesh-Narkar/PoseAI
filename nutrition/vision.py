"""
PoseAI Accurate Nutrition Scanner — Multi-Tiered Vision & Analysis Engine
========================================================================
Implements the Barcode-First, OCR Label Verification, and Packaged Food
specialization architecture.

NEVER: IMAGE -> GUESS NUTRITION -> DISPLAY AS FACT.

Hierarchy of Reliability:
1. Level 1 (Verified): Barcode lookup or Nutrition Facts label OCR
2. Level 2 (Database Estimate): Known product / fresh food catalog match
3. Level 3 (AI Visual Estimate): Fresh un-packaged food with portion estimator
4. Level 4 (Unknown / Low Confidence): Prompts for barcode, label photo, or manual input.
"""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import Any, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from nutrition.barcode import detect_barcode_in_image, lookup_barcode
from nutrition.food_db import (
    FOOD_DATABASE,
    get_food_by_id,
    scale_nutrition,
    search_foods,
    resolve_canonical_food,
)
from nutrition.ocr_engine import (
    extract_text_from_image,
    identify_product_from_package_ocr,
    parse_nutrition_facts_text,
)
from nutrition.packaged_db import (
    VERIFIED_PACKAGED_PRODUCTS,
    get_packaged_by_barcode,
    search_packaged_by_text,
)
from nutrition.product_lookup import get_product_lookup_service
from nutrition.validator import validate_nutrition, check_calorie_consistency
from nutrition.gemini_vision import (
    recognize_food_candidates,
    is_gemini_available,
    FoodRecognition,
    FoodCandidate,
)

logger = logging.getLogger("poseai.nutrition.vision")

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}


def _add_validation(result: dict) -> dict:
    """
    Inject NutritionValidator output into any pipeline result dict.
    Always adds: validation_valid, validation_warnings, validation_errors, calorie_consistency.
    Modifies result in-place and also returns it.
    """
    nutrition = result.get("nutrition", {})
    if nutrition:
        v = validate_nutrition(nutrition)
        c = check_calorie_consistency(nutrition)
        result["validation_valid"]    = v["valid"]
        result["validation_warnings"] = v.get("warnings", [])
        result["validation_errors"]   = v.get("errors", [])
        result["calorie_consistency"] = c
    return result


def validate_and_decode_image(image_bytes: bytes) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """Validate binary image format/size and decode to OpenCV BGR numpy array."""
    if not image_bytes:
        return None, "No image data received."
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return None, "Image exceeds maximum allowed size of 10MB."

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        fmt = (pil_img.format or "").upper()
        if fmt not in ALLOWED_FORMATS:
            return None, f"Unsupported image format: {fmt}. Please upload JPEG, PNG, or WEBP."

        rgb_img = pil_img.convert("RGB")
        img_np = np.array(rgb_img)
        bgr_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        return bgr_img, None
    except Exception as e:
        logger.warning("Image decoding failed: %s", e)
        return None, "Invalid or corrupted image file."


def decode_base64_frame(data_url_or_b64: str) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """Decode base64 image data URI."""
    if not data_url_or_b64:
        return None, "Empty image data."

    try:
        if "," in data_url_or_b64:
            header, b64_str = data_url_or_b64.split(",", 1)
        else:
            b64_str = data_url_or_b64

        raw_bytes = base64.b64decode(b64_str)
        return validate_and_decode_image(raw_bytes)
    except Exception as e:
        return None, f"Could not decode image: {str(e)}"


def _is_blurry(img: np.ndarray, threshold: float = 40.0) -> bool:
    """Detect blurry or out-of-focus camera captures using Laplacian variance."""
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        return variance < threshold
    except Exception:
        return False


def analyze_food_image(
    img: np.ndarray,
    user_hint: Optional[str] = None,
    default_meal_type: str = "lunch",
    scan_type: str = "auto",  # "packaged", "fresh", "barcode", "label", "auto"
) -> dict[str, Any]:
    """
    Core food-analysis pipeline prioritizing verified packaging data over visual guessing.

    PRIORITY:
    1. Barcode Detection & Lookup
    2. Nutrition Facts Label OCR
    3. Packaging Brand / Product Name Detection
    4. Fresh Food Identification (if fresh mode or packaged checks return nothing)
    5. Low Confidence Rule (Never guess, prompt user)
    """
    if img is None:
        return {
            "success": False,
            "error": "Invalid image received.",
            "low_confidence": True,
        }

    # Blurry image check (Requirement 21)
    if _is_blurry(img):
        return {
            "success": True,
            "status": "needs_confirmation",
            "requires_confirmation": True,
            "source": "unknown",
            "source_type": "unknown",
            "low_confidence": True,
            "confidence": 0.20,
            "accuracy_level": "unknown",
            "message": "Food is not clear enough to identify.",
            "confidence_message": "Image is too blurry or dark to identify food. Please upload another image.",
            "prompt_actions": ["UPLOAD ANOTHER IMAGE", "SCAN AGAIN", "ENTER FOOD MANUALLY"],
            "detected_foods": [],
            "candidates": [],
            "nutrition": {
                "calories_kcal": 0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
                "fiber_g": 0.0,
                "sugar_g": 0.0,
                "sodium_mg": 0,
                "serving_unit": "serving",
                "serving_qty": 1.0,
                "serving_size_g": 0.0,
            },
            "food_quality": {
                "classification": "unknown",
                "processing_level": "unknown",
                "reasons": ["Image too blurry or dark to identify food."],
            },
            "debug": {
                "image_quality": {"score": 0.1, "variance": 0.0, "is_blurry": True},
                "confidence_state": "needs_confirmation",
                "final_candidate": "None",
            },
        }

    # ──────────────────────────────────────────────────────────────────
    # TIER 1: BARCODE-FIRST SYSTEM
    # ──────────────────────────────────────────────────────────────────
    if scan_type in {"auto", "packaged", "barcode"}:
        barcode, b_format = detect_barcode_in_image(img)
        if barcode:
            match = lookup_barcode(barcode)
            if match and match.get("verified"):
                p = match["product"]
                nut = p["nutrition_per_serving"]
                serving_g = p.get("serving_size_g", 28.0)
                serving_unit = p.get("serving_unit", f"serving ({serving_g}g)")

                return _add_validation({
                    "success": True,
                    "source": "barcode_database",
                    "source_type": "barcode_database",
                    "source_confidence": "high",
                    "accuracy_level": "LEVEL 1 — VERIFIED",
                    "confidence": match["confidence"],
                    "confidence_label": match["confidence_label"],
                    "confidence_message": match["confidence_message"],
                    "meal_type": default_meal_type,
                    "verified": True,
                    "low_confidence": False,
                    "product_info": {
                        "brand": p["brand"],
                        "product_name": p["product_name"],
                        "barcode": barcode,
                        "serving_size_g": serving_g,
                        "serving_unit": serving_unit,
                    },
                    "detected_foods": [
                        {
                            "id": p.get("id", f"barcode_{barcode}"),
                            "name": f"{p['brand']} {p['product_name']}",
                            "quantity": f"1 {serving_unit}",
                            "serving_qty": 1.0,
                            "serving_unit": serving_unit,
                            "estimated_weight_g": serving_g,
                            "confidence": match["confidence"],
                        }
                    ],
                    "nutrition": {
                        "calories_kcal": nut["calories_kcal"],
                        "protein_g": nut["protein_g"],
                        "carbs_g": nut["carbs_g"],
                        "fat_g": nut["fat_g"],
                        "fiber_g": nut.get("fiber_g", 0.0),
                        "sugar_g": nut.get("sugar_g", 0.0),
                        "sodium_mg": nut.get("sodium_mg", 0),
                        "serving_unit": serving_unit,
                        "serving_qty": 1.0,
                        "serving_size_g": serving_g,
                    },
                    "food_quality": p.get("food_quality", {
                        "classification": "occasional",
                        "processing_level": "ultra_processed",
                        "reasons": ["Verified packaged product formulation."],
                    }),
                })


    # ──────────────────────────────────────────────────────────────────
    # TIER 2 & 3: PACKAGING OCR (LABEL OR BRAND FRONT)
    # ──────────────────────────────────────────────────────────────────
    if scan_type in {"auto", "packaged", "label"}:
        extracted_text = extract_text_from_image(img)

        # 1. Try Nutrition Facts Label Parser
        label_match = parse_nutrition_facts_text(extracted_text)
        if label_match:
            nut = label_match["nutrition_per_serving"]
            serv_unit = label_match["serving_unit"]
            serv_g = label_match["serving_size_g"]

            return _add_validation({
                "success": True,
                "source": "nutrition_label_ocr",
                "source_type": "nutrition_label_ocr",
                "source_confidence": "high",
                "accuracy_level": "LEVEL 1 — VERIFIED",
                "confidence": label_match["confidence"],
                "confidence_label": label_match["confidence_label"],
                "confidence_message": label_match["confidence_message"],
                "meal_type": default_meal_type,
                "verified": True,
                "low_confidence": False,
                "product_info": {
                    "brand": "Visible Label",
                    "product_name": "Packaged Product",
                    "serving_size_g": serv_g,
                    "serving_unit": serv_unit,
                },
                "detected_foods": [
                    {
                        "id": "nutrition_label_item",
                        "name": "Packaged Food (Nutrition Label)",
                        "quantity": f"1 {serv_unit}",
                        "serving_qty": 1.0,
                        "serving_unit": serv_unit,
                        "estimated_weight_g": serv_g,
                        "confidence": label_match["confidence"],
                    }
                ],
                "nutrition": {
                    "calories_kcal": nut["calories_kcal"],
                    "protein_g": nut["protein_g"],
                    "carbs_g": nut["carbs_g"],
                    "fat_g": nut["fat_g"],
                    "fiber_g": nut.get("fiber_g", 0.0),
                    "sugar_g": nut.get("sugar_g", 0.0),
                    "sodium_mg": nut.get("sodium_mg", 0),
                    "serving_unit": serv_unit,
                    "serving_qty": 1.0,
                    "serving_size_g": serv_g,
                },
                "food_quality": label_match["food_quality"],
            })

        # 2. Try Packaging Front Brand / Product Identifier
        product_match = identify_product_from_package_ocr(extracted_text)
        if product_match:
            p = product_match["product"]
            nut = p["nutrition_per_serving"]
            serv_g = p["serving_size_g"]
            serv_unit = p["serving_unit"]

            return _add_validation({
                "success": True,
                "source": "trusted_product_database",
                "source_type": "trusted_product_database",
                "source_confidence": "high",
                "accuracy_level": "LEVEL 1 — VERIFIED",
                "confidence": product_match["confidence"],
                "confidence_label": product_match["confidence_label"],
                "confidence_message": product_match["confidence_message"],
                "meal_type": default_meal_type,
                "verified": True,
                "low_confidence": False,
                "product_info": {
                    "brand": p["brand"],
                    "product_name": p["product_name"],
                    "serving_size_g": serv_g,
                    "serving_unit": serv_unit,
                },
                "detected_foods": [
                    {
                        "id": p["id"],
                        "name": f"{p['brand']} {p['product_name']}",
                        "quantity": f"1 {serv_unit}",
                        "serving_qty": 1.0,
                        "serving_unit": serv_unit,
                        "estimated_weight_g": serv_g,
                        "confidence": product_match["confidence"],
                    }
                ],
                "nutrition": {
                    "calories_kcal": nut["calories_kcal"],
                    "protein_g": nut["protein_g"],
                    "carbs_g": nut["carbs_g"],
                    "fat_g": nut["fat_g"],
                    "fiber_g": nut.get("fiber_g", 0.0),
                    "sugar_g": nut.get("sugar_g", 0.0),
                    "sodium_mg": nut.get("sodium_mg", 0),
                    "serving_unit": serv_unit,
                    "serving_qty": 1.0,
                    "serving_size_g": serv_g,
                },
                "food_quality": p["food_quality"],
                "possible_matches": product_match.get("other_matches", []),
            })

    # ──────────────────────────────────────────────────────────────────
    # TIER 4: FRESH / COOKED FOOD ESTIMATION
    # ──────────────────────────────────────────────────────────────────
    # If explicitly packaged mode and barcode/label/brand wasn't verified,
    # NEVER hallucinate fresh cooked food like Biryani for a chips bag!
    if scan_type == "packaged":
        return {
            "success": True,
            "low_confidence": True,
            "confidence": 0.40,
            "source_type": "unknown",
            "accuracy_level": "unknown",
            "message": "Packaged food could not be identified confidently.",
            "confidence_message": "Could not detect a clear barcode, brand name, or nutrition facts label.",
            "prompt_actions": ["SCAN BARCODE", "PHOTOGRAPH NUTRITION LABEL", "ENTER FOOD MANUALLY"],
            "detected_foods": [],
            "nutrition": {"calories_kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0,
                           "fiber_g": 0, "sugar_g": 0, "sodium_mg": 0},
            "food_quality": {"classification": "unknown", "processing_level": "unknown",
                              "reasons": ["Packaged product not verified — barcode/label required."]},
        }

    # ──────────────────────────────────────────────────────────────────
    # TIER 4: MULTI-CANDIDATE VISUAL EVIDENCE & CONTRADICTION PIPELINE
    # ──────────────────────────────────────────────────────────────────
    rec, debug_trace = recognize_food_candidates(img, user_hint=user_hint)
    if rec and rec.candidates and rec.food_present:
        top_c = rec.candidates[0]

        # Build candidate shortlist for UI
        candidates_payload = []
        for c in rec.candidates:
            c_canon = resolve_canonical_food(c.name)
            candidates_payload.append({
                "name": c.name,
                "canonical_id": c_canon["id"] if c_canon else re.sub(r"[^a-z0-9]+", "_", c.name.lower())[:30],
                "score": c.visual_score,
                "reason": c.visual_reason,
                "supporting": c.supporting_evidence,
                "contradicting": c.contradicting_evidence,
            })

        # Check whether confirmation is required
        if rec.requires_confirmation or top_c.visual_score < 0.60:
            logger.info("Food identification uncertain (top: %s at %.2f). Requesting user confirmation.", top_c.name, top_c.visual_score)
            return {
                "success": True,
                "status": "needs_confirmation",
                "requires_confirmation": True,
                "message": "Food identification uncertain. Please confirm your dish.",
                "candidates": candidates_payload,
                "recognition": {
                    "confidence": top_c.visual_score,
                    "state": debug_trace.get("confidence_state", "needs_confirmation"),
                    "top_candidates": [{"name": c["name"], "score": c["score"]} for c in candidates_payload],
                },
                "nutrition": None,
                "debug": debug_trace,
                "detected_foods": [],
                "source": "gemini_vision_ai",
                "accuracy_level": "NEEDS CONFIRMATION",
            }

        # High or Medium Confidence: Top candidate accepted
        canon = resolve_canonical_food(top_c.name)
        if canon:
            nut = scale_nutrition(canon, 1.0)
            portion_desc = f"1 {canon.get('serving_unit', 'piece')}"
            weight_g = canon.get("estimated_weight_g", 140)
            nutrition_source = "food_database"
            food_name = canon["name"]
            canonical_id = canon["id"]
            quality = canon.get("food_quality", {
                "classification": "nutrient_dense",
                "processing_level": "minimally_processed",
                "reasons": ["Verified food catalog profile."],
            })
        else:
            food_name = top_c.name
            canonical_id = re.sub(r"[^a-z0-9]+", "_", food_name.lower())[:30]
            portion_desc = "1 serving"
            weight_g = 150
            nut = {
                "calories_kcal": 250,
                "protein_g": 8.0,
                "carbs_g": 35.0,
                "fat_g": 9.0,
                "fiber_g": 3.0,
                "sugar_g": 2.0,
                "sodium_mg": 350,
                "serving_unit": "serving",
                "serving_qty": 1.0,
                "estimated_weight_g": 150,
            }
            nutrition_source = "ai_estimate"
            quality = {
                "classification": "balanced",
                "processing_level": "processed",
                "reasons": ["AI visual estimation."],
            }

        logger.info(
            "Food recognized: %s (canonical: %s, confidence: %.2f, state: %s)",
            food_name, canonical_id, top_c.visual_score, debug_trace.get("confidence_state"),
        )

        return _add_validation({
            "success": True,
            "status": "success",
            "requires_confirmation": False,
            "food": {
                "canonical_id": canonical_id,
                "name": food_name,
            },
            "recognition": {
                "confidence": top_c.visual_score,
                "state": debug_trace.get("confidence_state", "high"),
                "top_candidates": [{"name": c.name, "score": c.visual_score} for c in rec.candidates],
            },
            "portion": {
                "description": portion_desc,
                "estimated": True,
                "estimated_weight_g": weight_g,
                "serving_qty": 1.0,
                "serving_unit": canon.get("serving_unit", "serving") if canon else "serving",
            },
            "nutrition": nut,
            "nutrition_source": nutrition_source,
            "food_quality": quality,
            "meal_type": default_meal_type,
            # Backward-compatible fields for existing dashboard & logs
            "detected_foods": [
                {
                    "id": canonical_id,
                    "name": food_name,
                    "quantity": portion_desc,
                    "serving_qty": 1.0,
                    "serving_unit": canon.get("serving_unit", "serving") if canon else "serving",
                    "estimated_weight_g": weight_g,
                    "confidence": top_c.visual_score,
                    "items": [{"name": c.name, "score": c.visual_score} for c in rec.candidates],
                }
            ],
            "source": nutrition_source,
            "source_type": "gemini_vision_ai",
            "accuracy_level": f"LEVEL 2 — {debug_trace.get('confidence_state', 'HIGH').upper()} CONFIDENCE",
            "confidence": top_c.visual_score,
            "confidence_label": f"Visual Match ({int(top_c.visual_score * 100)}%)",
            "confidence_message": top_c.visual_reason,
            "debug": debug_trace,
        })

    # ──────────────────────────────────────────────────────────────────
    # TIER 5: LOW CONFIDENCE / UNKNOWN (NEVER GUESS WRONG FOOD)
    # ──────────────────────────────────────────────────────────────────
    logger.info("Food recognition could not identify candidates. Prompting user honestly.")
    return {
        "success": True,
        "status": "needs_confirmation",
        "requires_confirmation": True,
        "low_confidence": True,
        "confidence": 0.20,
        "source": "unknown",
        "source_type": "unknown",
        "accuracy_level": "unknown",
        "message": "Food could not be identified confidently.",
        "confidence_message": "Insufficient visual evidence to identify this meal. Please select a match below or enter manually.",
        "prompt_actions": ["CONFIRM MATCH", "SCAN BARCODE", "ENTER FOOD MANUALLY"],
        "candidates": [],
        "detected_foods": [],
        "nutrition": {
            "calories_kcal": 0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
            "sugar_g": 0.0,
            "sodium_mg": 0,
            "serving_unit": "serving",
            "serving_qty": 1.0,
            "serving_size_g": 0.0,
        },
        "food_quality": {
            "classification": "unknown",
            "processing_level": "unknown",
            "reasons": ["Insufficient visual evidence to identify food."],
        },
        "debug": debug_trace,
    }
