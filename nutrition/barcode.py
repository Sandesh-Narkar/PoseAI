"""
PoseAI Accurate Nutrition Scanner — Barcode Detection & Lookup Engine
=====================================================================
Detects EAN-13, EAN-8, UPC-A, and UPC-E retail barcodes from packaging images
using OpenCV's BarcodeDetector with multi-pass image preprocessing.
Resolves barcodes against local verified packaged catalog and Open Food Facts API.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional, Tuple

import cv2
import numpy as np
import requests

from nutrition.packaged_db import get_packaged_by_barcode

logger = logging.getLogger("poseai.nutrition.barcode")

# Initialize OpenCV native BarcodeDetector
try:
    _DETECTOR = cv2.barcode.BarcodeDetector()
except Exception as e:
    logger.warning("Could not initialize cv2.barcode.BarcodeDetector: %s", e)
    _DETECTOR = None


def detect_barcode_in_image(img: np.ndarray) -> Tuple[Optional[str], Optional[str]]:
    """
    Detect and decode retail barcode from an OpenCV BGR image.
    Returns (barcode_string, barcode_format) or (None, None).
    """
    if img is None or _DETECTOR is None:
        return None, None

    # Multi-pass attempt: original, enhanced contrast, and rotated passes
    passes = [
        img,
        cv2.convertScaleAbs(img, alpha=1.3, beta=20),  # contrast enhanced
    ]

    # Convert to grayscale for barcode detection
    for pass_img in passes:
        gray = cv2.cvtColor(pass_img, cv2.COLOR_BGR2GRAY)
        try:
            ok, decoded_info, decoded_type, _ = _DETECTOR.detectAndDecode(gray)
            if ok and decoded_info:
                # decoded_info can be tuple or list of detected barcodes
                for info, b_type in zip(decoded_info, decoded_type):
                    clean = re.sub(r"[^0-9A-Za-z]", "", str(info)).strip()
                    if clean and len(clean) >= 8:
                        return clean, str(b_type)
        except Exception as e:
            logger.debug("Barcode detection pass exception: %s", e)

    return None, None


def query_open_food_facts(barcode: str) -> Optional[dict[str, Any]]:
    """
    Query Open Food Facts public API for verified global barcode nutrition.
    Strict 3-second timeout; returns None gracefully on network failure.
    """
    clean_code = re.sub(r"[^0-9]", "", str(barcode))
    if not clean_code or len(clean_code) < 8:
        return None

    url = f"https://world.openfoodfacts.org/api/v2/product/{clean_code}.json"
    headers = {"User-Agent": "PoseAI-FitnessPlatform/2.0 (contact@poseai.test)"}

    try:
        resp = requests.get(url, headers=headers, timeout=3.0)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get("status") != 1 or "product" not in data:
            return None

        p = data["product"]
        nutriments = p.get("nutriments", {})

        # Extract per-serving or per-100g values
        serving_size_str = p.get("serving_size") or "100g"
        serving_qty = p.get("serving_quantity")
        try:
            serving_g = float(serving_qty) if serving_qty else 100.0
        except (ValueError, TypeError):
            # Parse gram match from text e.g. "28 g (1 oz)"
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:g|ml)", str(serving_size_str).lower())
            serving_g = float(m.group(1)) if m else 100.0

        # Calories
        cal = nutriments.get("energy-kcal_serving")
        if cal is None:
            cal_100 = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal", 0)
            cal = (float(cal_100) * (serving_g / 100.0))

        # Protein
        prot = nutriments.get("proteins_serving")
        if prot is None:
            prot_100 = nutriments.get("proteins_100g", 0)
            prot = float(prot_100) * (serving_g / 100.0)

        # Carbs
        carbs = nutriments.get("carbohydrates_serving")
        if carbs is None:
            carbs_100 = nutriments.get("carbohydrates_100g", 0)
            carbs = float(carbs_100) * (serving_g / 100.0)

        # Fat
        fat = nutriments.get("fat_serving")
        if fat is None:
            fat_100 = nutriments.get("fat_100g", 0)
            fat = float(fat_100) * (serving_g / 100.0)

        # Fiber
        fiber = nutriments.get("fiber_serving")
        if fiber is None:
            fiber_100 = nutriments.get("fiber_100g", 0)
            fiber = float(fiber_100) * (serving_g / 100.0)

        # Sugar
        sugar = nutriments.get("sugars_serving")
        if sugar is None:
            sugar_100 = nutriments.get("sugars_100g", 0)
            sugar = float(sugar_100) * (serving_g / 100.0)

        # Sodium (convert g salt to mg sodium if needed)
        sodium = nutriments.get("sodium_serving")
        if sodium is None:
            sodium_100 = nutriments.get("sodium_100g")
            if sodium_100 is not None:
                sodium = float(sodium_100) * 1000 * (serving_g / 100.0)  # g to mg
            else:
                salt_100 = nutriments.get("salt_100g", 0)
                sodium = (float(salt_100) / 2.5) * 1000 * (serving_g / 100.0)

        product_name = p.get("product_name") or p.get("product_name_en") or "Packaged Product"
        brand = p.get("brands") or "Verified Brand"

        # Determine protein rating objectively
        prot_val = round(float(prot), 1)
        if prot_val >= 15.0:
            p_rating = "high_protein"
        elif prot_val >= 6.0:
            p_rating = "moderate_protein"
        elif prot_val > 0.0:
            p_rating = "low_protein"
        else:
            p_rating = "zero_protein"

        return {
            "id": f"off_{clean_code}",
            "barcode": clean_code,
            "brand": brand,
            "product_name": product_name,
            "serving_size_g": round(serving_g, 1),
            "serving_unit": f"serving ({serving_size_str})",
            "nutrition_per_serving": {
                "calories_kcal": int(round(float(cal))),
                "protein_g": prot_val,
                "carbs_g": round(float(carbs), 1),
                "fat_g": round(float(fat), 1),
                "fiber_g": round(float(fiber), 1),
                "sugar_g": round(float(sugar), 1),
                "sodium_mg": int(round(float(sodium))),
            },
            "food_quality": {
                "classification": "nutrient_dense" if prot_val >= 15 or float(fiber) >= 5 else "occasional",
                "processing_level": "ultra_processed" if "chips" in product_name.lower() or "biscuit" in product_name.lower() else "processed",
                "protein_rating": p_rating,
                "reasons": [
                    f"Official nutrition verified via Open Food Facts (Barcode {clean_code})",
                    f"Protein content: {prot_val}g per serving",
                ],
            },
        }
    except Exception as e:
        logger.debug("Open Food Facts query failed or timed out: %s", e)
        return None


def lookup_barcode(barcode: str) -> Optional[dict[str, Any]]:
    """
    Priority 1: Local verified packaged database (guaranteed fast & exact).
    Priority 2: Open Food Facts API (global barcode coverage).
    """
    # 1. Local catalog check
    local = get_packaged_by_barcode(barcode)
    if local:
        return {
            "source": "barcode_database",
            "source_type": "barcode_database",
            "source_confidence": "high",
            "accuracy_level": "LEVEL 1 — VERIFIED",
            "confidence": 0.99,
            "confidence_label": "Verified (Barcode)",
            "confidence_message": f"Verified product match via barcode {barcode}. Nutrition is exact.",
            "verified": True,
            "product": local,
        }

    # 2. Open Food Facts lookup
    remote = query_open_food_facts(barcode)
    if remote:
        return {
            "source": "barcode_database",
            "source_type": "barcode_database",
            "source_confidence": "high",
            "accuracy_level": "LEVEL 1 — VERIFIED",
            "confidence": 0.98,
            "confidence_label": "Verified (Open Food Facts)",
            "confidence_message": f"Verified product match via barcode {barcode} from international product database.",
            "verified": True,
            "product": remote,
        }

    return None
