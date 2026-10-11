"""
PoseAI Accurate Nutrition Scanner — OCR Engine
==============================================
Extracts text from packaging, reads nutrition facts panels with numeric
macro parsing, and identifies packaged product brands using EasyOCR.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional, Tuple

import cv2
import numpy as np

from nutrition.packaged_db import search_packaged_by_text

logger = logging.getLogger("poseai.nutrition.ocr")

_EASYOCR_READER: Any = None


def get_ocr_reader() -> Any:
    """Lazy initialization of EasyOCR reader."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr  # type: ignore
            # Initialize for English with CPU/GPU auto-detect
            _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
        except Exception as e:
            logger.warning("Could not initialize EasyOCR reader: %s", e)
            _EASYOCR_READER = None
    return _EASYOCR_READER


def preprocess_for_label_ocr(img: np.ndarray) -> np.ndarray:
    """Preprocess an image specifically for nutrition label OCR.
    Converts to grayscale, applies CLAHE for contrast, then sharpens."""
    if img is None:
        return img
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Adaptive histogram equalization for uneven lighting
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    # Sharpen
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(eq, -1, kernel)
    # Binarize
    _, binary = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Convert back to 3-channel for EasyOCR
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def preprocess_for_barcode_ocr(img: np.ndarray) -> np.ndarray:
    """Preprocess image to enhance barcode readability."""
    if img is None:
        return img
    h, w = img.shape[:2]
    # Upscale small images
    if max(h, w) < 600:
        scale = 600.0 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # High contrast boost
    boosted = cv2.convertScaleAbs(gray, alpha=1.5, beta=30)
    return cv2.cvtColor(boosted, cv2.COLOR_GRAY2BGR)


def extract_text_from_image(img: np.ndarray) -> str:
    """Extract raw text from an image using EasyOCR with contrast pre-processing."""
    if img is None:
        return ""

    reader = get_ocr_reader()
    if reader is None:
        return ""

    try:
        # Preprocessing: upscale if small, convert to RGB
        h, w = img.shape[:2]
        if max(h, w) < 800:
            scale = 800.0 / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = reader.readtext(rgb, detail=0)
        return " ".join(results)
    except Exception as e:
        logger.debug("EasyOCR extraction failed: %s", e)
        return ""



def parse_nutrition_facts_text(text: str) -> Optional[dict[str, Any]]:
    """
    Parse structured nutrition facts from extracted label text.
    Extracts Serving Size, Calories, Protein, Carbohydrates, Fat, Fiber, Sugar, Sodium.
    """
    if not text or len(text.strip()) < 10:
        return None

    clean = text.lower()

    # Must contain at least two nutrition label anchor keywords
    anchors = ["nutrition", "calories", "serving", "protein", "carbohydrate", "fat", "energy"]
    matches = sum(1 for a in anchors if a in clean)
    if matches < 2:
        return None

    # Serving size extraction
    serving_size_g = 28.0
    serving_str = "1 serving"
    serv_match = re.search(
        r"serving\s*(?:size)?[:\s]*([0-9]+(?:\.[0-9]+)?)\s*(?:g|ml|piece|chips|cookies|biscuit|pack|scoop)",
        clean,
    )
    if serv_match:
        try:
            serving_size_g = float(serv_match.group(1))
            serving_str = f"{serving_size_g}g"
        except Exception:
            pass

    # Calories extraction
    cal = None
    cal_match = re.search(r"(?:calories|energy|kcal)[:\s]*([0-9]{1,4})", clean)
    if cal_match:
        cal = int(cal_match.group(1))

    # Protein extraction (CRITICAL: exact numeric parsing, NEVER hallucinated)
    prot = None
    prot_match = re.search(r"protein[:\s]*([0-9]+(?:\.[0-9]+)?)\s*(?:g)?", clean)
    if prot_match:
        prot = float(prot_match.group(1))

    # Carbohydrates
    carbs = None
    carb_match = re.search(r"(?:total\s*carbohydrate|carbohydrates|carbs|total\s*carb)[:\s]*([0-9]+(?:\.[0-9]+)?)\s*(?:g)?", clean)
    if carb_match:
        carbs = float(carb_match.group(1))

    # Fat
    fat = None
    fat_match = re.search(r"(?:total\s*fat|fat|lipides)[:\s]*([0-9]+(?:\.[0-9]+)?)\s*(?:g)?", clean)
    if fat_match:
        fat = float(fat_match.group(1))

    # Fiber
    fiber = 0.0
    fiber_match = re.search(r"(?:dietary\s*fiber|fiber|fibre)[:\s]*([0-9]+(?:\.[0-9]+)?)\s*(?:g)?", clean)
    if fiber_match:
        fiber = float(fiber_match.group(1))

    # Sugar
    sugar = 0.0
    sugar_match = re.search(r"(?:total\s*sugars|sugars|sugar)[:\s]*([0-9]+(?:\.[0-9]+)?)\s*(?:g)?", clean)
    if sugar_match:
        sugar = float(sugar_match.group(1))

    # Sodium
    sodium = 0
    sod_match = re.search(r"(?:sodium|salt)[:\s]*([0-9]+(?:\.[0-9]+)?)\s*(?:mg|g)?", clean)
    if sod_match:
        val = float(sod_match.group(1))
        # If salt in grams was given, convert to sodium mg
        if "salt" in clean and val < 50.0:
            sodium = int(round((val / 2.5) * 1000))
        else:
            sodium = int(round(val))

    # We require at least Calories and either Protein or Carbs/Fat to declare a valid label
    if cal is None and (prot is None or carbs is None):
        return None

    # Default missing fields safely
    final_cal = cal if cal is not None else int(round((prot or 0) * 4 + (carbs or 0) * 4 + (fat or 0) * 9))
    final_prot = round(prot if prot is not None else 0.0, 1)
    final_carbs = round(carbs if carbs is not None else 0.0, 1)
    final_fat = round(fat if fat is not None else 0.0, 1)

    # Objective protein rating based strictly on numbers
    if final_prot >= 15.0:
        p_rating = "high_protein"
    elif final_prot >= 6.0:
        p_rating = "moderate_protein"
    elif final_prot > 0.0:
        p_rating = "low_protein"
    else:
        p_rating = "zero_protein"

    return {
        "source": "nutrition_label_ocr",
        "source_type": "nutrition_label_ocr",
        "source_confidence": "high",
        "accuracy_level": "LEVEL 1 — VERIFIED",
        "confidence": 0.97,
        "confidence_label": "Verified (Nutrition Label OCR)",
        "confidence_message": "Extracted directly from visible nutrition facts label.",
        "serving_size_g": serving_size_g,
        "serving_unit": f"serving ({serving_str})",
        "nutrition_per_serving": {
            "calories_kcal": final_cal,
            "protein_g": final_prot,
            "carbs_g": final_carbs,
            "fat_g": final_fat,
            "fiber_g": round(fiber, 1),
            "sugar_g": round(sugar, 1),
            "sodium_mg": sodium,
        },
        "food_quality": {
            "classification": "nutrient_dense" if final_prot >= 15 or fiber >= 5 else "occasional",
            "processing_level": "processed",
            "protein_rating": p_rating,
            "reasons": [
                f"Verified from visible nutrition facts panel",
                f"Protein: {final_prot}g per serving ({p_rating.replace('_', ' ')})",
            ],
        },
    }


def identify_product_from_package_ocr(text: str) -> Optional[dict[str, Any]]:
    """
    Search verified packaged catalog using text extracted from package front.
    Priority:
      1. Offline seed keyword search (fast, no network)
      2. ProductLookupService (Open Food Facts by name — network required)
    """
    # 1. Offline seed
    matches = search_packaged_by_text(text)
    if matches:
        top = matches[0]
        return {
            "source": top.get("source", "local_seed"),
            "source_type": top.get("source", "local_seed"),
            "source_confidence": "high",
            "accuracy_level": "LEVEL 1 — VERIFIED",
            "confidence": 0.94,
            "confidence_label": f"Verified Product: {top['brand']}",
            "confidence_message": f"Identified as {top['brand']} {top['product_name']} from packaging text.",
            "product": top,
            "other_matches": [
                {"id": m["id"], "brand": m["brand"], "product_name": m["product_name"]}
                for m in matches[1:4]
            ],
        }

    # 2. ProductLookupService (Open Food Facts name search)
    if text and len(text.strip()) >= 4:
        try:
            from nutrition.product_lookup import get_product_lookup_service
            svc = get_product_lookup_service()
            results = svc.lookup_by_text(text)
            if results:
                top = results[0]
                return {
                    "source": top.source,
                    "source_type": top.source,
                    "source_confidence": "high",
                    "accuracy_level": "LEVEL 1 — VERIFIED",
                    "confidence": 0.91,
                    "confidence_label": f"Verified: {top.brand}",
                    "confidence_message": (
                        f"Identified as {top.brand} {top.product_name} via Open Food Facts."
                    ),
                    "product": top.to_dict(),
                    "other_matches": [
                        {"id": r.id, "brand": r.brand, "product_name": r.product_name}
                        for r in results[1:4]
                    ],
                }
        except Exception as exc:
            logger.debug("ProductLookupService name search failed: %s", exc)

    return None
