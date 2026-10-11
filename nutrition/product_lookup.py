"""
PoseAI Accurate Nutrition Scanner — ProductLookupService
=========================================================
Central service for all product identification and nutrition retrieval.

Lookup priority per barcode:
  1. MongoDB food_cache  (if result < 30 days old)
  2. Open Food Facts API (live)
  3. Offline seed        (network-unavailable fallback)
  4. Returns None        → caller shows "product not found" prompt

By-name search:
  - Open Food Facts search API
  - Offline seed keyword search as fallback
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from nutrition.packaged_db import get_packaged_by_barcode, search_packaged_by_text

logger = logging.getLogger("poseai.nutrition.product_lookup")

_OFF_USER_AGENT = "PoseAI-FitnessPlatform/2.0 (contact@poseai.test)"
_OFF_BASE       = "https://world.openfoodfacts.org"
_REQUEST_TIMEOUT = 4.0   # seconds
_CACHE_TTL_DAYS  = 30


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class ProductResult:
    id: str
    barcode: Optional[str]
    brand: str
    product_name: str
    serving_size_g: float
    serving_unit: str
    nutrition_per_serving: dict[str, Any]
    food_quality: dict[str, Any]
    source: str          # "open_food_facts" | "local_seed"
    source_url: str
    verified: bool
    fetched_at: str      # ISO timestamp
    keywords: list[str] = field(default_factory=list)
    raw: Optional[dict[str, Any]] = None  # original API payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "barcode": self.barcode,
            "brand": self.brand,
            "product_name": self.product_name,
            "serving_size_g": self.serving_size_g,
            "serving_unit": self.serving_unit,
            "nutrition_per_serving": self.nutrition_per_serving,
            "food_quality": self.food_quality,
            "source": self.source,
            "source_url": self.source_url,
            "verified": self.verified,
            "fetched_at": self.fetched_at,
        }


# ---------------------------------------------------------------------------
# Open Food Facts normalizer
# ---------------------------------------------------------------------------
def _normalize_off_product(p: dict[str, Any], barcode: Optional[str] = None) -> Optional[ProductResult]:
    """
    Normalize a raw Open Food Facts product dict into a ProductResult.
    Returns None if essential nutrition data is missing.
    """
    nutriments = p.get("nutriments", {})

    # Serving size
    serving_size_str = p.get("serving_size") or "100g"
    serving_qty_raw  = p.get("serving_quantity")
    try:
        serving_g = float(serving_qty_raw) if serving_qty_raw else None
    except (ValueError, TypeError):
        serving_g = None
    if serving_g is None or serving_g <= 0:
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:g|ml)", str(serving_size_str).lower())
        serving_g = float(m.group(1)) if m else 100.0

    scale = serving_g / 100.0

    def _get(per_serv_key: str, per100_key: str, default: float = 0.0) -> float:
        val = nutriments.get(per_serv_key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
        val100 = nutriments.get(per100_key, default)
        try:
            return float(val100) * scale
        except (ValueError, TypeError):
            return default

    cal   = _get("energy-kcal_serving", "energy-kcal_100g")
    prot  = _get("proteins_serving",     "proteins_100g")
    carbs = _get("carbohydrates_serving","carbohydrates_100g")
    fat   = _get("fat_serving",          "fat_100g")
    fiber = _get("fiber_serving",        "fiber_100g")
    sugar = _get("sugars_serving",       "sugars_100g")

    # Sodium: prefer sodium field, else derive from salt
    sodium_val = nutriments.get("sodium_serving")
    if sodium_val is None:
        sodium_100 = nutriments.get("sodium_100g")
        if sodium_100 is not None:
            sodium_mg = float(sodium_100) * 1000 * scale
        else:
            salt_100 = nutriments.get("salt_100g", 0.0)
            sodium_mg = (float(salt_100) / 2.5) * 1000 * scale
    else:
        # sodium_serving is in grams in OFF — convert to mg
        try:
            sv = float(sodium_val)
            sodium_mg = sv * 1000 if sv < 10 else sv  # already mg if > 10
        except (ValueError, TypeError):
            sodium_mg = 0.0

    # Require at least calories to be non-zero
    if cal <= 0 and prot <= 0 and carbs <= 0:
        return None

    product_name = (
        p.get("product_name")
        or p.get("product_name_en")
        or p.get("abbreviated_product_name")
        or "Packaged Product"
    )
    brand = p.get("brands") or "Unknown Brand"
    bc    = barcode or p.get("code") or ""

    # Protein rating (objective)
    prot_r = float(round(prot, 1))
    if prot_r >= 15.0:
        p_rating = "high_protein"
    elif prot_r >= 6.0:
        p_rating = "moderate_protein"
    elif prot_r > 0.0:
        p_rating = "low_protein"
    else:
        p_rating = "zero_protein"

    # Food quality from ingredient info
    additives_n = p.get("additives_n", 0) or 0
    nova_group  = p.get("nova_group")
    if nova_group == 4 or additives_n >= 5:
        proc_level = "ultra_processed"
        classification = "occasional"
    elif nova_group == 3 or additives_n >= 2:
        proc_level = "processed"
        classification = "occasional"
    elif prot_r >= 15 or float(round(fiber, 1)) >= 5:
        proc_level = "minimally_processed"
        classification = "nutrient_dense"
    else:
        proc_level = "processed"
        classification = "occasional"

    return ProductResult(
        id=f"off_{re.sub(r'[^0-9a-z_]', '_', product_name.lower()[:40])}",
        barcode=bc or None,
        brand=brand,
        product_name=product_name,
        serving_size_g=round(serving_g, 1),
        serving_unit=f"serving ({serving_size_str})",
        nutrition_per_serving={
            "calories_kcal": int(round(cal)),
            "protein_g":     round(prot, 1),
            "carbs_g":       round(carbs, 1),
            "fat_g":         round(fat, 1),
            "fiber_g":       round(fiber, 1),
            "sugar_g":       round(sugar, 1),
            "sodium_mg":     int(round(sodium_mg)),
        },
        food_quality={
            "classification":   classification,
            "processing_level": proc_level,
            "protein_rating":   p_rating,
            "reasons": [
                f"Verified via Open Food Facts (barcode {bc})" if bc else "Verified via Open Food Facts",
                f"Protein: {prot_r}g per serving ({p_rating.replace('_', ' ')})",
            ],
        },
        source="open_food_facts",
        source_url=f"https://world.openfoodfacts.org/product/{bc}" if bc else _OFF_BASE,
        verified=True,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        raw=p,
    )


def _seed_to_product_result(seed: dict[str, Any]) -> ProductResult:
    """Convert an offline seed dict to a ProductResult."""
    return ProductResult(
        id=seed["id"],
        barcode=seed.get("barcode"),
        brand=seed["brand"],
        product_name=seed["product_name"],
        serving_size_g=seed["serving_size_g"],
        serving_unit=seed["serving_unit"],
        nutrition_per_serving=seed["nutrition_per_serving"],
        food_quality=seed["food_quality"],
        source="local_seed",
        source_url=seed.get("source_url", ""),
        verified=True,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        keywords=seed.get("keywords", []),
    )


# ---------------------------------------------------------------------------
# MongoDB food_cache helpers (lazy import to avoid circular deps)
# ---------------------------------------------------------------------------
def _get_db():
    from database import mongo as mongo_db
    return mongo_db.get_db()


def _get_cached(barcode: str) -> Optional[dict[str, Any]]:
    """Return cached product dict if < CACHE_TTL_DAYS old, else None."""
    try:
        from datetime import timedelta
        db = _get_db()
        doc = db["food_cache"].find_one({"barcode": barcode})
        if not doc:
            return None
        fetched = doc.get("fetched_at")
        if isinstance(fetched, datetime):
            age_days = (datetime.now(timezone.utc) - fetched.replace(tzinfo=timezone.utc)).days
            if age_days > _CACHE_TTL_DAYS:
                return None
        return doc.get("product_data")
    except Exception as exc:
        logger.debug("food_cache read failed: %s", exc)
        return None


def _put_cache(barcode: str, product: ProductResult) -> None:
    """Store a verified product result in MongoDB food_cache."""
    try:
        db = _get_db()
        db["food_cache"].update_one(
            {"barcode": barcode},
            {"$set": {
                "barcode": barcode,
                "product_data": product.to_dict(),
                "source": product.source,
                "source_url": product.source_url,
                "fetched_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as exc:
        logger.debug("food_cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# ProductLookupService
# ---------------------------------------------------------------------------
class ProductLookupService:
    """
    Central service for product identification and nutrition retrieval.

    All methods return ProductResult | None, never raise.
    """

    # ── Barcode lookup ────────────────────────────────────────────────────

    def lookup_by_barcode(self, barcode: str) -> Optional[ProductResult]:
        """
        Priority:
          1. MongoDB food_cache  (fast, < 30d TTL)
          2. Open Food Facts API
          3. Offline seed
        """
        if not barcode:
            return None
        clean = re.sub(r"[^0-9]", "", barcode)
        if len(clean) < 8:
            return None

        # 1. Cache
        cached = _get_cached(clean)
        if cached:
            logger.debug("food_cache HIT for barcode %s", clean)
            return ProductResult(**{k: cached.get(k) for k in ProductResult.__dataclass_fields__ if k in cached})

        # 2. Open Food Facts
        result = self._query_off_barcode(clean)
        if result:
            _put_cache(clean, result)
            return result

        # 3. Offline seed
        seed = get_packaged_by_barcode(clean)
        if seed:
            logger.debug("Offline seed match for barcode %s", clean)
            return _seed_to_product_result(seed)

        return None

    def _query_off_barcode(self, barcode: str) -> Optional[ProductResult]:
        url = f"{_OFF_BASE}/api/v2/product/{barcode}.json"
        try:
            resp = requests.get(url, headers={"User-Agent": _OFF_USER_AGENT}, timeout=_REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("status") != 1 or "product" not in data:
                return None
            return _normalize_off_product(data["product"], barcode)
        except Exception as exc:
            logger.debug("OFF barcode query failed: %s", exc)
            return None

    # ── Name / text search ────────────────────────────────────────────────

    def search_by_name(self, query: str, limit: int = 5) -> list[ProductResult]:
        """
        Search Open Food Facts by product name.
        Falls back to offline seed keyword search.
        """
        if not query or not query.strip():
            return []

        results = self._search_off_by_name(query.strip(), limit)
        if not results:
            results = self._search_seed(query, limit)
        return results[:limit]

    def _search_off_by_name(self, query: str, limit: int) -> list[ProductResult]:
        """Query OFF search API."""
        try:
            resp = requests.get(
                f"{_OFF_BASE}/cgi/search.pl",
                params={
                    "search_terms": query,
                    "search_simple": "1",
                    "action": "process",
                    "json": "1",
                    "page_size": str(min(limit * 2, 20)),
                    "sort_by": "unique_scans_n",
                },
                headers={"User-Agent": _OFF_USER_AGENT},
                timeout=_REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            products = data.get("products", [])
            results = []
            for p in products:
                pr = _normalize_off_product(p)
                if pr:
                    results.append(pr)
                    if len(results) >= limit:
                        break
            return results
        except Exception as exc:
            logger.debug("OFF name search failed: %s", exc)
            return []

    def _search_seed(self, query: str, limit: int) -> list[ProductResult]:
        """Search offline seed by keyword."""
        matches = search_packaged_by_text(query)
        return [_seed_to_product_result(s) for s in matches[:limit]]

    # ── Convenience ───────────────────────────────────────────────────────

    def lookup_by_text(self, text: str) -> list[ProductResult]:
        """Search by arbitrary text (brand + product name from OCR output)."""
        return self.search_by_name(text, limit=5)


# Module-level singleton
_service = ProductLookupService()


def get_product_lookup_service() -> ProductLookupService:
    return _service
