"""
PoseAI Accurate Nutrition Scanner — Packaged Food Offline Seed
==============================================================
Small offline seed of verified products used ONLY when the network is
unavailable. Values sourced from each brand's official published nutrition panel.

Primary lookup priority:
  1. MongoDB food_cache (cached real API results, TTL 30 days)
  2. Open Food Facts API  (via ProductLookupService)
  3. This offline seed    (last resort / offline fallback only)

DO NOT add invented or uncertain product data to this file.
"""

from __future__ import annotations

import re
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Offline Seed — 10 most common Indian / global packaged products
# All values from official printed nutrition labels, not invented.
# ---------------------------------------------------------------------------
_OFFLINE_SEED: list[dict[str, Any]] = [
    {
        "id": "lays_classic_salted_seed",
        "barcode": "8901491101837",
        "barcodes": ["8901491101837", "028400017053"],
        "brand": "Lay's",
        "product_name": "Classic Salted Potato Chips",
        "category": "chips_snacks",
        "serving_size_g": 26.0,
        "serving_unit": "serving (26g)",
        "source": "local_seed",
        "source_url": "https://www.pepsicoindia.com/products/lays",
        "nutrition_per_serving": {
            "calories_kcal": 130,
            "protein_g": 1.8,
            "carbs_g": 14.0,
            "fat_g": 7.6,
            "fiber_g": 0.9,
            "sugar_g": 0.2,
            "sodium_mg": 160,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["Deep-fried, high sodium, low protein (1.8g/serving)"],
        },
        "keywords": ["lays", "lays classic", "potato chips", "salted chips"],
    },
    {
        "id": "kurkure_masala_seed",
        "barcode": "8901491501019",
        "barcodes": ["8901491501019"],
        "brand": "Kurkure",
        "product_name": "Masala Munch",
        "category": "chips_snacks",
        "serving_size_g": 26.0,
        "serving_unit": "serving (26g)",
        "source": "local_seed",
        "source_url": "https://www.pepsicoindia.com/products/kurkure",
        "nutrition_per_serving": {
            "calories_kcal": 128,
            "protein_g": 2.0,
            "carbs_g": 16.0,
            "fat_g": 6.2,
            "fiber_g": 0.5,
            "sugar_g": 0.8,
            "sodium_mg": 200,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["Extruded snack, high sodium"],
        },
        "keywords": ["kurkure", "masala munch", "kurkure masala"],
    },
    {
        "id": "maggi_2min_seed",
        "barcode": "8901058000011",
        "barcodes": ["8901058000011"],
        "brand": "Maggi",
        "product_name": "2-Minute Masala Noodles",
        "category": "instant_noodles",
        "serving_size_g": 70.0,
        "serving_unit": "serving (1 pack / 70g)",
        "source": "local_seed",
        "source_url": "https://www.maggiindia.com",
        "nutrition_per_serving": {
            "calories_kcal": 310,
            "protein_g": 7.0,
            "carbs_g": 47.0,
            "fat_g": 11.0,
            "fiber_g": 1.0,
            "sugar_g": 1.5,
            "sodium_mg": 800,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["High sodium (800mg), refined flour base"],
        },
        "keywords": ["maggi", "2 minute noodles", "maggi noodles", "instant noodles"],
    },
    {
        "id": "oreo_original_seed",
        "barcode": "7622210100252",
        "barcodes": ["7622210100252", "8901571001252"],
        "brand": "Oreo",
        "product_name": "Original Sandwich Cookies",
        "category": "biscuits_cookies",
        "serving_size_g": 34.0,
        "serving_unit": "serving (3 cookies / 34g)",
        "source": "local_seed",
        "source_url": "https://www.nabiscoworld.com/oreo",
        "nutrition_per_serving": {
            "calories_kcal": 160,
            "protein_g": 1.0,
            "carbs_g": 25.0,
            "fat_g": 7.0,
            "fiber_g": 1.0,
            "sugar_g": 14.0,
            "sodium_mg": 135,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["14g sugar per serving, ultra-processed"],
        },
        "keywords": ["oreo", "oreo cookies", "sandwich cookies", "oreo biscuit"],
    },
    {
        "id": "coca_cola_330ml_seed",
        "barcode": "5449000000996",
        "barcodes": ["5449000000996", "8901012018022"],
        "brand": "Coca-Cola",
        "product_name": "Original Taste",
        "category": "soft_drinks",
        "serving_size_g": 330.0,
        "serving_unit": "serving (1 can / 330ml)",
        "source": "local_seed",
        "source_url": "https://www.coca-colacompany.com",
        "nutrition_per_serving": {
            "calories_kcal": 139,
            "protein_g": 0.0,
            "carbs_g": 35.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
            "sugar_g": 35.0,
            "sodium_mg": 40,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["35g sugar per can, zero protein/fiber"],
        },
        "keywords": ["coca cola", "coke", "cola", "soft drink", "cold drink"],
    },
    {
        "id": "dairy_milk_silk_seed",
        "barcode": "7622300489236",
        "barcodes": ["7622300489236", "8901063120082"],
        "brand": "Cadbury",
        "product_name": "Dairy Milk Silk",
        "category": "chocolate",
        "serving_size_g": 60.0,
        "serving_unit": "serving (1 bar / 60g)",
        "source": "local_seed",
        "source_url": "https://www.cadburyindia.com",
        "nutrition_per_serving": {
            "calories_kcal": 317,
            "protein_g": 4.9,
            "carbs_g": 34.9,
            "fat_g": 17.8,
            "fiber_g": 0.5,
            "sugar_g": 31.2,
            "sodium_mg": 55,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": ["High sugar and fat, moderate protein from milk solids"],
        },
        "keywords": ["dairy milk", "dairy milk silk", "cadbury silk", "cadbury chocolate"],
    },
    {
        "id": "amul_gold_milk_seed",
        "barcode": "8901735000178",
        "barcodes": ["8901735000178"],
        "brand": "Amul",
        "product_name": "Gold Full Cream Milk",
        "category": "dairy",
        "serving_size_g": 200.0,
        "serving_unit": "serving (200ml)",
        "source": "local_seed",
        "source_url": "https://www.amul.com",
        "nutrition_per_serving": {
            "calories_kcal": 134,
            "protein_g": 6.4,
            "carbs_g": 9.6,
            "fat_g": 7.6,
            "fiber_g": 0.0,
            "sugar_g": 9.6,
            "sodium_mg": 100,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": ["Good protein source, calcium-rich"],
        },
        "keywords": ["amul gold", "amul milk", "full cream milk", "amul"],
    },
    {
        "id": "britannia_marie_seed",
        "barcode": "8901063103054",
        "barcodes": ["8901063103054"],
        "brand": "Britannia",
        "product_name": "Marie Gold Biscuits",
        "category": "biscuits_cookies",
        "serving_size_g": 32.5,
        "serving_unit": "serving (5 biscuits / 32.5g)",
        "source": "local_seed",
        "source_url": "https://www.britannia.co.in",
        "nutrition_per_serving": {
            "calories_kcal": 138,
            "protein_g": 2.8,
            "carbs_g": 24.3,
            "fat_g": 3.5,
            "fiber_g": 0.5,
            "sugar_g": 5.5,
            "sodium_mg": 120,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": ["Moderate sugar, refined flour"],
        },
        "keywords": ["britannia", "marie gold", "marie biscuit", "marie"],
    },
    {
        "id": "monster_energy_seed",
        "barcode": "5060128488014",
        "barcodes": ["5060128488014", "070847811015"],
        "brand": "Monster Energy",
        "product_name": "Original Green Energy Drink",
        "category": "energy_drinks",
        "serving_size_g": 500.0,
        "serving_unit": "serving (1 can / 500ml)",
        "source": "local_seed",
        "source_url": "https://www.monsterenergy.com",
        "nutrition_per_serving": {
            "calories_kcal": 190,
            "protein_g": 0.0,
            "carbs_g": 47.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
            "sugar_g": 47.0,
            "sodium_mg": 360,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["Very high sugar (47g), zero protein/fiber"],
        },
        "keywords": ["monster", "monster energy", "energy drink"],
    },
    {
        "id": "horlicks_original_seed",
        "barcode": "8901070030069",
        "barcodes": ["8901070030069"],
        "brand": "Horlicks",
        "product_name": "Original Health Drink",
        "category": "health_drinks",
        "serving_size_g": 32.0,
        "serving_unit": "serving (4 tbsp / 32g)",
        "source": "local_seed",
        "source_url": "https://www.horlicks.in",
        "nutrition_per_serving": {
            "calories_kcal": 117,
            "protein_g": 3.7,
            "carbs_g": 22.4,
            "fat_g": 1.6,
            "fiber_g": 0.4,
            "sugar_g": 9.0,
            "sodium_mg": 80,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": ["Fortified malted drink, moderate sugar"],
        },
        "keywords": ["horlicks", "horlicks original", "health drink", "malt drink"],
    },
]

# ---------------------------------------------------------------------------
# Index builders — O(1) barcode lookup, scored keyword search
# ---------------------------------------------------------------------------
_BARCODE_INDEX: dict[str, dict[str, Any]] = {}
_KEYWORD_INDEX: list[tuple[list[str], dict[str, Any]]] = []

for _p in _OFFLINE_SEED:
    for _bc in _p.get("barcodes", []):
        _BARCODE_INDEX[re.sub(r"[^0-9]", "", _bc)] = _p
    _KEYWORD_INDEX.append((_p.get("keywords", []), _p))


def get_packaged_by_barcode(barcode: str) -> Optional[dict[str, Any]]:
    """Return offline seed product for barcode, or None if not in seed."""
    if not barcode:
        return None
    return _BARCODE_INDEX.get(re.sub(r"[^0-9]", "", str(barcode)))


def search_packaged_by_text(text: str) -> list[dict[str, Any]]:
    """Search offline seed by keyword match. Returns ranked results."""
    if not text:
        return []
    clean = text.lower()
    scored: list[tuple[int, dict[str, Any]]] = []
    for keywords, product in _KEYWORD_INDEX:
        score = sum(1 for kw in keywords if kw in clean)
        if score > 0:
            scored.append((score, product))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored]


def get_all_offline_products() -> list[dict[str, Any]]:
    """Return the full offline seed list (diagnostics / testing)."""
    return list(_OFFLINE_SEED)


# Legacy alias kept for backward compat with barcode.py / ocr_engine.py
VERIFIED_PACKAGED_PRODUCTS = _OFFLINE_SEED
