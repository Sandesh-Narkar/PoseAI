"""
PoseAI Nutrition Assistant — USDA FoodData Central Integration
=============================================================
Provides nutrition lookup for fresh/whole foods NOT in the Indian food database.

Uses USDA FoodData Central API (Foundation Foods + SR Legacy datasets).
API key read from USDA_API_KEY environment variable.

Falls back gracefully when:
- USDA_API_KEY is not set → silently skip (Indian food DB still works)
- API request fails / times out → return None
- No matching food found → return None

Results are cached in MongoDB food_cache with a 7-day TTL to avoid
re-fetching identical queries.

Docs: https://fdc.nal.usda.gov/api-guide.html
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

import requests

logger = logging.getLogger("poseai.nutrition.usda_db")

_USDA_BASE = "https://api.nal.usda.gov/fdc/v1"
_REQUEST_TIMEOUT = 5.0
_CACHE_TTL_DAYS = 7

# Standard portion: 100g base for USDA normalization
_USDA_BASE_G = 100.0


# ---------------------------------------------------------------------------
# Internal schema
# ---------------------------------------------------------------------------

def _empty_nutrition() -> dict[str, Any]:
    return {
        "calories_kcal": 0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0,
    }


# USDA nutrient ID → our field name
_NUTRIENT_MAP = {
    1008: "calories_kcal",   # Energy (kcal)
    1003: "protein_g",       # Protein
    1005: "carbs_g",         # Carbohydrate, by difference
    1004: "fat_g",           # Total lipid (fat)
    1079: "fiber_g",         # Fiber, total dietary
    2000: "sugar_g",         # Sugars, total
    1093: "sodium_mg",       # Sodium
}


# ---------------------------------------------------------------------------
# MongoDB cache helpers
# ---------------------------------------------------------------------------

def _get_db():
    from database import mongo as mongo_db
    return mongo_db.get_db()


def _cache_key(query: str) -> str:
    return "usda_" + re.sub(r"[^a-z0-9]", "_", query.lower().strip())


def _get_cached_usda(query: str) -> Optional[dict[str, Any]]:
    try:
        from datetime import timedelta
        db = _get_db()
        key = _cache_key(query)
        doc = db["food_cache"].find_one({"barcode": key, "type": "usda"})
        if not doc:
            return None
        fetched = doc.get("fetched_at")
        if isinstance(fetched, datetime):
            age_days = (datetime.now(timezone.utc) - fetched.replace(tzinfo=timezone.utc)).days
            if age_days > _CACHE_TTL_DAYS:
                return None
        return doc.get("product_data")
    except Exception as exc:
        logger.debug("USDA cache read failed: %s", exc)
        return None


def _put_cached_usda(query: str, nutrition: dict[str, Any], food_name: str) -> None:
    try:
        db = _get_db()
        key = _cache_key(query)
        db["food_cache"].update_one(
            {"barcode": key, "type": "usda"},
            {"$set": {
                "barcode": key,
                "type": "usda",
                "query": query,
                "food_name": food_name,
                "product_data": nutrition,
                "fetched_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as exc:
        logger.debug("USDA cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# USDA API
# ---------------------------------------------------------------------------

def _get_api_key() -> Optional[str]:
    key = os.environ.get("USDA_API_KEY", "").strip()
    return key if key else None


def _extract_nutrients(food_item: dict[str, Any], portion_g: float) -> dict[str, Any]:
    """Extract and scale nutrients from a USDA food item to portion_g."""
    nut = _empty_nutrition()
    scale = portion_g / _USDA_BASE_G

    food_nutrients = food_item.get("foodNutrients", [])
    for fn in food_nutrients:
        nutrient_id = fn.get("nutrientId") or fn.get("nutrient", {}).get("id")
        value_per100 = fn.get("value")
        if nutrient_id in _NUTRIENT_MAP and value_per100 is not None:
            field = _NUTRIENT_MAP[nutrient_id]
            try:
                scaled_val = float(value_per100) * scale
                if field == "calories_kcal":
                    nut[field] = int(round(scaled_val))
                elif field == "sodium_mg":
                    # USDA sometimes stores sodium in mg/100g, sometimes g/100g
                    if float(value_per100) < 10:
                        scaled_val = float(value_per100) * 1000 * scale
                    nut[field] = int(round(scaled_val))
                else:
                    nut[field] = round(scaled_val, 1)
            except (TypeError, ValueError):
                pass

    return nut


def _search_usda_api(query: str, api_key: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Query USDA FoodData Central search endpoint."""
    try:
        resp = requests.post(
            f"{_USDA_BASE}/foods/search",
            json={
                "query": query,
                "dataType": ["Foundation", "SR Legacy", "Branded"],
                "pageSize": max_results,
                "sortBy": "dataType.keyword",
                "sortOrder": "asc",
            },
            params={"api_key": api_key},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.debug("USDA API returned %d for query %r", resp.status_code, query)
            return []
        data = resp.json()
        return data.get("foods", [])
    except Exception as exc:
        logger.debug("USDA API request failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_usda(food_name: str, portion_g: float = 100.0) -> Optional[dict[str, Any]]:
    """
    Look up nutrition for a fresh/whole food using USDA FoodData Central.

    Returns a nutrition dict scaled to portion_g, or None if:
    - USDA_API_KEY not set
    - No matching food found
    - API request fails

    The returned dict includes:
    {
        "calories_kcal": int,
        "protein_g": float,
        "carbs_g": float,
        "fat_g": float,
        "fiber_g": float,
        "sugar_g": float,
        "sodium_mg": int,
        "source": "usda_fdc",
        "food_name": str,
        "portion_g": float,
    }
    """
    if not food_name or not food_name.strip():
        return None

    api_key = _get_api_key()
    if not api_key:
        logger.debug("USDA_API_KEY not set — skipping USDA lookup")
        return None

    query = food_name.strip().lower()

    # Check cache first
    cached = _get_cached_usda(query)
    if cached:
        # Re-scale cached 100g base to requested portion
        cached_portion = cached.get("portion_g", 100.0)
        if abs(cached_portion - portion_g) > 1.0:
            scale = portion_g / cached_portion
            rescaled = {k: (round(v * scale, 1) if isinstance(v, float) else int(round(v * scale)))
                        for k, v in cached.items()
                        if k in ("calories_kcal", "protein_g", "carbs_g",
                                  "fat_g", "fiber_g", "sugar_g", "sodium_mg")}
            rescaled.update({"source": "usda_fdc", "food_name": cached.get("food_name", food_name),
                              "portion_g": portion_g})
            return rescaled
        return cached

    # API call
    foods = _search_usda_api(query, api_key)
    if not foods:
        return None

    # Pick the best match (Foundation or SR Legacy preferred over Branded)
    best = None
    for food in foods:
        dt = food.get("dataType", "")
        if dt in ("Foundation", "SR Legacy"):
            best = food
            break
    if best is None:
        best = foods[0]

    food_description = best.get("description", food_name)
    nut = _extract_nutrients(best, portion_g)

    # Require at least calories to be non-zero
    if nut["calories_kcal"] <= 0:
        return None

    result = {
        **nut,
        "source": "usda_fdc",
        "food_name": food_description,
        "portion_g": portion_g,
    }

    # Cache at the requested portion_g
    _put_cached_usda(query, result, food_description)
    logger.info("USDA lookup: %r → %r (%d kcal / %dg)", query, food_description,
                nut["calories_kcal"], int(portion_g))
    return result


def is_usda_available() -> bool:
    """Return True if USDA_API_KEY is configured."""
    return bool(os.environ.get("USDA_API_KEY", "").strip())
