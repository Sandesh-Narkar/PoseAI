"""
PoseAI - Fitness Market Data Layer

MongoDB storage for the Fitness Market storefront:
    market_products    product catalog (real + demo seed)
    market_categories  browse categories
    market_carts       one cart document per authenticated user

Shares the single database.mongo connection, so in dev mode
(MONGO_ALLOW_MOCK=1) the market transparently uses the same in-memory
mongomock database as the rest of the application (auth + workouts).

Storage contract (all user_id values are the hex ObjectId string kept in
the Flask session):
    market_products: {
        "_id": ObjectId, "name": str, "slug": str, "description": str,
        "brand": str, "category": str, "price": float,
        "original_price": float, "discount_percentage": int,
        "image_url": str, "rating": float, "review_count": int,
        "stock_quantity": int, "tags": [str], "is_active": bool,
        "is_deal": bool, "is_demo": bool,
        "created_at": datetime(UTC), "updated_at": datetime(UTC),
    }
    market_categories: {
        "_id": ObjectId, "slug": str, "label": str, "icon": str,
        "tagline": str, "sort_order": int, "is_active": bool,
    }
    market_carts: {
        "_id": ObjectId, "user_id": str,
        "items": [{"product_id": str, "quantity": int, "added_at": datetime}],
        "updated_at": datetime,
    }

Money is ALWAYS recomputed from the product documents. Amounts sent by the
browser are never trusted (see build_cart_payload).
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING

from database import mongo as mongo_db

logger = logging.getLogger("poseai.market")

# Re-exported so callers can catch it without importing database.mongo too.
MongoUnavailableError = mongo_db.MongoUnavailableError


class MarketError(Exception):
    """Base class for Fitness Market domain errors."""


class ProductNotFoundError(MarketError):
    """Raised when a product id does not resolve to an active product."""


class OutOfStockError(MarketError):
    """Raised when a product is unavailable or the requested quantity exceeds stock."""


MAX_CART_QUANTITY = 10
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 48

# Demo catalog is only inserted while the products collection is empty.
SEED_FLAG_ENV = "MARKET_SEED_DEMO"

INDEXES_ENSURED = False

SEARCH_FIELDS = ("name", "brand", "category", "tags")


def _seed_enabled() -> bool:
    """Demo seeding is ON by default and can be disabled with MARKET_SEED_DEMO=0."""
    raw = os.getenv(SEED_FLAG_ENV)
    if raw is None or raw.strip() == "":
        return True
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_indexes(database: Any) -> None:
    """Create the indexes backing the market collections. Best-effort."""
    try:
        database["market_products"].create_index([("slug", ASCENDING)], unique=True)
        database["market_products"].create_index(
            [("category", ASCENDING), ("price", ASCENDING)]
        )
        database["market_categories"].create_index([("slug", ASCENDING)], unique=True)
        database["market_carts"].create_index([("user_id", ASCENDING)], unique=True)
    except Exception:  # noqa: BLE001 - index creation is best-effort
        logger.warning("Could not create Fitness Market indexes (best-effort).")


def _db() -> Any:
    global INDEXES_ENSURED
    database = mongo_db.get_db()
    if not INDEXES_ENSURED:
        _ensure_indexes(database)
        INDEXES_ENSURED = True
    return database


def get_products_collection() -> Any:
    return _db()["market_products"]


def get_categories_collection() -> Any:
    return _db()["market_categories"]


def get_carts_collection() -> Any:
    return _db()["market_carts"]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return slug.strip("-")


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

# ==============================================================================
#  DEMO CATALOG
# ==============================================================================
# Inserted ONLY while the market_products collection is empty, so a real
# MongoDB catalog can replace it at any time (every query below reads from the
# collections, never from these constants). Disable with MARKET_SEED_DEMO=0.
# Demo rows are flagged is_demo=True.

_DEMO_CATEGORIES = [
    ("protein", "Protein", "sports_bar", "Whey, isolate, plant and mass gainers", 10),
    ("creatine", "Creatine", "bolt", "Monohydrate, micronized and capsules", 20),
    ("pre-workout", "Pre-Workout", "local_fire_department", "Energy and focus formulas", 30),
    ("bcaa", "BCAA", "science", "BCAA and essential amino acids", 40),
    ("vitamins", "Vitamins", "medication", "Daily multivitamins, D3 and omega-3", 50),
    ("recovery", "Recovery", "healing", "Electrolytes and recovery formulas", 60),
    ("health-wellness", "Health & Wellness", "spa", "Greens, joints and sleep support", 70),
    ("apparel", "Apparel", "checkroom", "Training tees, shorts and gloves", 80),
    ("accessories", "Gym Accessories", "fitness_center", "Bands, belts, shakers and mats", 90),
]

# name, brand, category, price, original_price, rating, reviews, stock, deal, tags, description
_DEMO_PRODUCTS = [
    ("Whey Protein Isolate", "IronForge", "protein", 2599, 3299, 4.6, 1284, 20, True,
     "protein,whey,isolate,muscle gain", "Fast-absorbing whey isolate with 27g protein and minimal lactose per scoop."),
    ("Whey Protein Concentrate", "CoreFuel", "protein", 1799, 2199, 4.4, 862, 34, False,
     "protein,whey,concentrate,daily", "Everyday whey concentrate that mixes clean and supports lean recovery."),
    ("Plant Protein Blend", "VitaCore", "protein", 2099, 2499, 4.3, 431, 18, False,
     "protein,plant,vegan,dairy free", "Pea and brown rice protein blend for a smooth plant-based shake."),
    ("Mass Gainer XXL", "IronForge", "protein", 2899, 3499, 4.5, 987, 12, True,
     "protein,mass gainer,calories,bulk", "High-calorie gainer built for hard gainers chasing size and strength."),
    ("Creatine Monohydrate", "CoreFuel", "creatine", 899, 1199, 4.7, 2103, 40, True,
     "creatine,monohydrate,strength,power", "Micronised creatine monohydrate for strength, power and training volume."),
    ("Micronized Creatine Powder", "PeakForm", "creatine", 1049, 1399, 4.5, 764, 26, False,
     "creatine,powder,unflavoured,power", "Unflavoured micronised creatine that dissolves fully in water or shakes."),
    ("Creatine Capsules", "VitaCore", "creatine", 1199, 1499, 4.2, 388, 15, False,
     "creatine,capsules,travel,easy", "Convenient creatine capsules for travel days and busy training weeks."),
    ("Pre-Workout Ignite", "PeakForm", "pre-workout", 1499, 1899, 4.4, 612, 22, False,
     "pre-workout,energy,focus,pump", "Balanced pre-workout for steady energy and sharp training focus."),
    ("Energy Formula Zero Sugar", "CoreFuel", "pre-workout", 1299, 1599, 4.1, 355, 30, False,
     "pre-workout,energy,zero sugar,stim", "Sugar-free pre-training formula with a moderate caffeine profile."),
    ("BCAA 2:1:1 Powder", "PeakForm", "bcaa", 1149, 1449, 4.3, 421, 24, False,
     "bcaa,aminos,intra workout,endurance", "Classic 2:1:1 BCAA ratio for intra-workout sipping and endurance."),
    ("Recovery Aminos EAA", "EnduraLabs", "bcaa", 1399, 1699, 4.5, 508, 19, False,
     "bcaa,eaa,aminos,recovery", "Full essential amino acid profile to support recovery between sessions."),
    ("Daily Multivitamin", "VitaCore", "vitamins", 649, 849, 4.6, 1520, 60, True,
     "vitamins,multivitamin,daily,immunity", "Complete daily multivitamin covering the common micronutrient gaps."),
    ("Vitamin D3 + K2", "VitaCore", "vitamins", 499, 699, 4.5, 890, 55, False,
     "vitamins,vitamin d,bones,indoor training", "D3 with K2 for bone and muscle support, useful for indoor training."),
    ("Omega-3 Fish Oil", "VitaCore", "vitamins", 799, 1049, 4.4, 705, 48, False,
     "vitamins,omega 3,joints,heart", "Purified omega-3 softgels supporting joints and everyday wellness."),
    ("Electrolyte Hydration Mix", "EnduraLabs", "recovery", 549, 699, 4.6, 1120, 50, True,
     "recovery,electrolytes,hydration,heat", "Electrolyte blend for hydration during long or hot training sessions."),
    ("Muscle Recovery Formula", "EnduraLabs", "recovery", 1699, 2099, 4.3, 402, 16, False,
     "recovery,muscle,tart cherry,rest", "Post-session recovery formula designed to support muscle repair."),
    ("Post-Workout Recovery Drink", "CoreFuel", "recovery", 1299, 1599, 4.2, 288, 21, False,
     "recovery,carbs,protein,post workout", "Carb and protein recovery drink for the window right after training."),
    ("Greens Superfood Blend", "VitaCore", "health-wellness", 1099, 1399, 4.2, 366, 27, False,
     "health,greens,superfood,fibre", "Greens blend with fibre and phytonutrients for daily wellness support."),
    ("Joint Support Complex", "EnduraLabs", "health-wellness", 999, 1299, 4.1, 244, 33, False,
     "health,joints,glucosamine,mobility", "Joint support complex for lifters handling heavier training loads."),
    ("Sleep & Recovery Support", "VitaCore", "health-wellness", 849, 1099, 4.3, 412, 29, False,
     "health,sleep,recovery,rest", "Magnesium-led night-time formula supporting rest and next-day readiness."),
    ("Performance Training Tee", "FlexLine", "apparel", 899, 1299, 4.4, 534, 45, True,
     "apparel,tshirt,training,sweat wicking", "Sweat-wicking training tee cut for full range of motion."),
    ("Flex Training Shorts", "FlexLine", "apparel", 1099, 1499, 4.3, 471, 38, False,
     "apparel,shorts,training,stretch", "Four-way stretch training shorts with a secure phone pocket."),
    ("Grip Training Gloves", "GripGear", "apparel", 749, 999, 4.5, 622, 42, False,
     "apparel,gloves,grip,lifting", "Padded lifting gloves that protect your palms on heavy pulling days."),
    ("Resistance Band Set", "GripGear", "accessories", 999, 1399, 4.6, 1340, 52, True,
     "accessories,bands,resistance,home workout", "Five-level resistance band set for warm-ups and home training."),
    ("Steel Shaker Bottle 700ml", "GripGear", "accessories", 499, 699, 4.7, 1890, 80, False,
     "accessories,shaker,bottle,leak proof", "Leak-proof stainless shaker that keeps shakes cold for hours."),
    ("Weightlifting Belt", "IronForge", "accessories", 1899, 2499, 4.5, 703, 14, False,
     "accessories,belt,lifting,core", "Leather lifting belt for bracing and confidence on heavy compounds."),
    ("Premium Yoga Mat 6mm", "FlexLine", "accessories", 1299, 1799, 4.4, 815, 25, False,
     "accessories,yoga mat,mobility,stretch", "Cushioned 6mm mat for mobility work, stretching and core sessions."),
]
# ==============================================================================
#  SERIALIZATION
# ==============================================================================

def _iso(value: Any) -> Optional[str]:
    """Serialize a datetime to ISO-8601, tolerating None or already-serialized values."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def product_to_dict(doc: dict) -> dict:
    """Public JSON shape for a single product document.

    Money fields are recomputed here (never trusted from the client) and the
    stock label is derived from stock_quantity so the storefront can render
    "In Stock" / "Only N left" / "Out of Stock" consistently.
    """
    stock = _to_int(doc.get("stock_quantity", 0))
    price = round(_to_float(doc.get("price")), 2)
    original = round(_to_float(doc.get("original_price"), price), 2)
    if original < price:
        original = price
    discount_percentage = _to_int(doc.get("discount_percentage"), 0)
    if discount_percentage <= 0 and original > price:
        discount_percentage = int(round((original - price) / original * 100))
    active = bool(doc.get("is_active", True))
    if stock <= 0 or not active:
        stock_label = "Out of Stock"
    elif stock <= 5:
        stock_label = "Only %d left" % stock
    else:
        stock_label = "In Stock"
    return {
        "id": str(doc.get("_id")),
        "name": doc.get("name") or "",
        "slug": doc.get("slug") or "",
        "description": doc.get("description") or "",
        "brand": doc.get("brand") or "",
        "category": doc.get("category") or "",
        "price": price,
        "original_price": original,
        "discount_percentage": discount_percentage,
        "image_url": doc.get("image_url") or "",
        "rating": round(_to_float(doc.get("rating")), 1),
        "review_count": _to_int(doc.get("review_count")),
        "stock_quantity": stock,
        "in_stock": stock > 0 and active,
        "stock_label": stock_label,
        "tags": list(doc.get("tags") or []),
        "is_deal": bool(doc.get("is_deal", False)),
        "is_demo": bool(doc.get("is_demo", False)),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
    }


def category_to_dict(doc: dict) -> dict:
    """Public JSON shape for a single category document."""
    return {
        "slug": doc.get("slug") or "",
        "label": doc.get("label") or "",
        "icon": doc.get("icon") or "fitness_center",
        "tagline": doc.get("tagline") or "",
        "sort_order": _to_int(doc.get("sort_order"), 100),
    }
# ==============================================================================
#  SEEDING / CATEGORIES
# ==============================================================================

def ensure_seed_data() -> dict:
    """Insert the demo catalog ONLY while the products collection is empty.

    Real MongoDB product documents therefore always win: once any product
    exists, this function is a no-op. Disable entirely with MARKET_SEED_DEMO=0.
    """
    products = get_products_collection()
    try:
        if products.count_documents({}) > 0:
            return {"seeded": False, "categories": 0, "products": 0}
    except Exception:  # noqa: BLE001
        return {"seeded": False, "categories": 0, "products": 0}
    if not _seed_enabled():
        return {"seeded": False, "categories": 0, "products": 0}

    categories = get_categories_collection()
    created_categories = 0
    for slug, label, icon, tagline, order in _DEMO_CATEGORIES:
        categories.update_one(
            {"slug": slug},
            {"$setOnInsert": {
                "slug": slug,
                "label": label,
                "icon": icon,
                "tagline": tagline,
                "sort_order": order,
                "is_active": True,
            }},
            upsert=True,
        )
        created_categories += 1

    now = now_utc()
    docs = []
    for row in _DEMO_PRODUCTS:
        (name, brand, category, price, original,
         rating, reviews, stock, deal, tags, blurb) = row
        original = max(_to_float(original, price), _to_float(price))
        price = _to_float(price)
        discount = int(round((original - price) / original * 100)) if original > price else 0
        docs.append({
            "name": name,
            "slug": _slugify(name),
            "description": blurb,
            "brand": brand,
            "category": category,
            "price": round(price, 2),
            "original_price": round(original, 2),
            "discount_percentage": discount,
            "image_url": "",
            "rating": _to_float(rating),
            "review_count": _to_int(reviews),
            "stock_quantity": _to_int(stock),
            "tags": [t.strip() for t in str(tags).split(",") if t.strip()],
            "is_active": True,
            "is_deal": bool(deal),
            "is_demo": True,
            "created_at": now,
            "updated_at": now,
        })
    inserted = 0
    if docs:
        products.insert_many(docs)
        inserted = len(docs)
    logger.info("Fitness Market demo catalog seeded (%d products)", inserted)
    return {"seeded": True, "categories": created_categories, "products": inserted}


def list_categories() -> list:
    """Active categories, ordered for the rail + chip bar."""
    ensure_seed_data()
    docs = get_categories_collection().find({"is_active": True}).sort(
        [("sort_order", ASCENDING), ("label", ASCENDING)]
    )
    return [category_to_dict(d) for d in docs]


def list_brands() -> list:
    """Distinct brands present in the catalog (drives the brand filter)."""
    ensure_seed_data()
    try:
        return sorted(b for b in get_products_collection().distinct("brand") if b)
    except Exception:  # noqa: BLE001
        return []


def get_product(product_id: Any) -> dict:
    """Fetch one active product by id. Raises ProductNotFoundError."""
    try:
        oid = ObjectId(str(product_id))
    except (InvalidId, TypeError, ValueError):
        raise ProductNotFoundError("Unknown product.")
    doc = get_products_collection().find_one({"_id": oid, "is_active": True})
    if doc is None:
        raise ProductNotFoundError("Unknown product.")
    return doc
# ==============================================================================
#  CATALOG QUERIES (search / filter / sort / paginate)
# ==============================================================================

# Supported ?sort= values -> Mongo sort specification.
SORT_OPTIONS = {
    "recommended": [("is_deal", DESCENDING), ("rating", DESCENDING), ("review_count", DESCENDING)],
    "price_asc": [("price", ASCENDING)],
    "price_desc": [("price", DESCENDING)],
    "popularity": [("review_count", DESCENDING), ("rating", DESCENDING)],
    "newest": [("created_at", DESCENDING)],
}


def _search_clause(search: str):
    """Case-insensitive match across name, brand, category and tags."""
    term = str(search or "").strip()
    if not term:
        return None
    pattern = re.escape(term)
    return [
        {"name": {"$regex": pattern, "$options": "i"}},
        {"brand": {"$regex": pattern, "$options": "i"}},
        {"category": {"$regex": pattern, "$options": "i"}},
        {"tags": {"$regex": pattern, "$options": "i"}},
    ]


def _as_list(value: Any) -> list:
    """Normalise a possibly-repeated query parameter into a list of strings."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def list_products(
    category: str = "",
    search: str = "",
    sort: str = "recommended",
    page: Any = 1,
    limit: Any = DEFAULT_PAGE_SIZE,
    brand: Any = None,
    min_price: Any = None,
    max_price: Any = None,
    in_stock: bool = False,
    deals: bool = False,
) -> tuple:
    """Return (products, pagination) for the storefront grid.

    Every filter is applied server-side so the browser can never widen the
    result set by manipulating the query string.
    """
    ensure_seed_data()
    query = {"is_active": True}

    selected = str(category or "").strip().lower()
    if selected and selected != "all":
        query["category"] = selected

    if deals:
        query["is_deal"] = True

    brands = _as_list(brand)
    if brands:
        query["brand"] = {"$in": brands}

    price_range = {}
    if min_price is not None and str(min_price).strip() != "":
        price_range["$gte"] = _to_float(min_price)
    if max_price is not None and str(max_price).strip() != "":
        price_range["$lte"] = _to_float(max_price)
    if price_range:
        query["price"] = price_range

    if in_stock:
        query["stock_quantity"] = {"$gt": 0}

    search_clause = _search_clause(search)
    if search_clause:
        query["$or"] = search_clause

    page_number = max(1, _to_int(page, 1))
    page_size = min(MAX_PAGE_SIZE, max(1, _to_int(limit, DEFAULT_PAGE_SIZE)))

    collection = get_products_collection()
    total = collection.count_documents(query)
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    if page_number > pages:
        page_number = pages

    sort_key = str(sort or "recommended").strip().lower()
    sort_spec = SORT_OPTIONS.get(sort_key, SORT_OPTIONS["recommended"])
    cursor = (
        collection.find(query)
        .sort(list(sort_spec) + [("_id", ASCENDING)])
        .skip((page_number - 1) * page_size)
        .limit(page_size)
    )
    products = [product_to_dict(doc) for doc in cursor]

    pagination = {
        "page": page_number,
        "limit": page_size,
        "total": total,
        "pages": pages,
        "has_next": page_number < pages,
        "has_prev": page_number > 1,
    }
    return products, pagination


# Goal (from the existing fitness profile) -> suggested browsing categories.
# These are general fitness shopping suggestions only, never medical advice.
GOAL_RECOMMENDATIONS = {
    "gain weight": ("protein", "creatine", "recovery"),
    "improve strength": ("creatine", "protein", "pre-workout"),
    "lose weight": ("vitamins", "recovery", "health-wellness"),
    "maintain weight": ("protein", "vitamins", "recovery"),
    "improve mobility": ("accessories", "recovery", "health-wellness"),
    "improve general fitness": ("protein", "vitamins", "accessories"),
}


def recommended_for_goal(goal: Optional[str]) -> dict:
    """Map the user's existing fitness goal to general storefront suggestions."""
    key = str(goal or "").strip().lower()
    slugs = GOAL_RECOMMENDATIONS.get(key, ("protein", "recovery", "vitamins"))
    products = []
    for slug in slugs:
        rows, _ = list_products(category=slug, sort="popularity", limit=3)
        products.extend(rows[:2])
    seen = set()
    unique = []
    for item in products:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        unique.append(item)
    return {"goal": goal or None, "categories": list(slugs), "products": unique[:6]}
# ==============================================================================
#  CART
# ==============================================================================
# One document per authenticated user, keyed by the server-side session id.
# The browser only ever sends product_id + quantity: prices, discounts,
# subtotals and totals are ALWAYS recomputed from the product documents, and
# quantities are clamped to both MAX_CART_QUANTITY and the real stock level.

def _cart_id(user_id: Any) -> str:
    uid = str(user_id or "").strip()
    if not uid:
        raise MarketError("An authenticated user is required.")
    return uid


def _get_cart_doc(user_id: Any) -> dict:
    """Raw cart document (never raises when the user has no cart yet)."""
    uid = _cart_id(user_id)
    doc = get_carts_collection().find_one({"user_id": uid})
    if doc is None:
        return {"user_id": uid, "items": []}
    return doc


def _ensure_cart_doc(user_id: Any) -> dict:
    """Create the cart document on first write (idempotent upsert)."""
    uid = _cart_id(user_id)
    now = now_utc()
    get_carts_collection().update_one(
        {"user_id": uid},
        {
            "$setOnInsert": {
                "user_id": uid,
                "items": [],
                "created_at": now,
            },
            "$set": {"updated_at": now},
        },
        upsert=True,
    )
    return get_carts_collection().find_one({"user_id": uid})


def build_cart_payload(user_id: Any) -> dict:
    """Cart document -> money payload, recomputed entirely server-side.

    subtotal  = sum(original_price * qty)   (list / MRP total)
    discount  = sum((original - price) * qty)  (savings)
    total     = subtotal - discount          (amount payable)
    """
    doc = _get_cart_doc(user_id)
    lines = []
    subtotal = 0.0
    discount = 0.0
    item_count = 0

    for entry in doc.get("items") or []:
        try:
            product = get_product(entry.get("product_id"))
        except ProductNotFoundError:
            # Deleted / deactivated product: drop the line instead of
            # surfacing a broken entry, without touching other carts.
            continue
        data = product_to_dict(product)
        requested = max(1, _to_int(entry.get("quantity"), 1))
        stock = data["stock_quantity"]
        available = stock > 0
        quantity = min(requested, stock) if available else requested
        line_mrp = round(data["original_price"] * quantity, 2)
        line_price = round(data["price"] * quantity, 2)
        line_discount = round(line_mrp - line_price, 2)
        if available:
            subtotal += line_mrp
            discount += line_discount
            item_count += quantity
        lines.append({
            "product_id": data["id"],
            "name": data["name"],
            "brand": data["brand"],
            "category": data["category"],
            "image_url": data["image_url"],
            "price": data["price"],
            "original_price": data["original_price"],
            "discount_percentage": data["discount_percentage"],
            "quantity": quantity,
            "requested_quantity": requested,
            "stock_quantity": stock,
            "in_stock": available,
            "stock_label": data["stock_label"],
            "line_total": line_price,
            "line_mrp": line_mrp,
            "line_discount": line_discount,
        })

    subtotal = round(subtotal, 2)
    discount = round(discount, 2)
    return {
        "items": lines,
        "item_count": item_count,
        "line_count": len(lines),
        "subtotal": subtotal,
        "discount": discount,
        "total": round(subtotal - discount, 2),
        "currency": "INR",
        "updated_at": _iso(doc.get("updated_at")),
    }

def _find_cart_line(user_id: Any, product_id: str) -> Optional[dict]:
    """Return the stored cart line for a product, or None when absent."""
    doc = _get_cart_doc(user_id)
    for line in doc.get("items") or []:
        if str(line.get("product_id")) == str(product_id):
            return line
    return None


def set_cart_quantity(user_id: Any, product_id: Any, quantity: Any = 1) -> dict:
    """Add a product to the cart, or change the quantity of an existing line.

    The browser only ever supplies product_id + quantity. Every monetary
    value is recomputed from the product document by build_cart_payload(),
    and the quantity is clamped to the real stock level so a client can
    never order more than exists.

    Raises:
        ProductNotFoundError - unknown / inactive product id
        OutOfStockError      - product unavailable, or quantity above stock
        MarketError          - malformed quantity
    """
    uid = _cart_id(user_id)
    product = get_product(product_id)
    data = product_to_dict(product)

    if not data["is_active"] and not product.get("is_active", True):
        raise ProductNotFoundError("This product is no longer available.")

    stock = data["stock_quantity"]

    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        raise MarketError("Quantity must be a whole number.")

    # quantity 0 (or negative) is a removal request, never a stored value.
    if qty <= 0:
        return remove_cart_item(uid, data["id"])

    if stock <= 0:
        raise OutOfStockError("%s is out of stock." % data["name"])
    if qty > stock:
        raise OutOfStockError(
            "Only %d left in stock for %s." % (stock, data["name"])
        )
    if qty > MAX_CART_QUANTITY:
        qty = MAX_CART_QUANTITY

    _ensure_cart_doc(uid)
    carts = get_carts_collection()
    now = now_utc()

    if _find_cart_line(uid, data["id"]) is not None:
        carts.update_one(
            {"user_id": uid, "items.product_id": data["id"]},
            {"$set": {"items.$.quantity": qty, "updated_at": now}},
        )
    else:
        carts.update_one(
            {"user_id": uid},
            {
                "$push": {
                    "items": {
                        "product_id": data["id"],
                        "quantity": qty,
                        "added_at": now,
                    }
                },
                "$set": {"updated_at": now},
            },
        )

    return build_cart_payload(uid)


def remove_cart_item(user_id: Any, product_id: Any) -> dict:
    """Remove one product line from the user's cart (idempotent)."""
    uid = _cart_id(user_id)
    pid = str(product_id or "").strip()
    _ensure_cart_doc(uid)
    if pid:
        get_carts_collection().update_one(
            {"user_id": uid},
            {
                "$pull": {"items": {"product_id": pid}},
                "$set": {"updated_at": now_utc()},
            },
        )
    return build_cart_payload(uid)


def clear_cart(user_id: Any) -> dict:
    """Empty the user's cart without deleting the cart document."""
    uid = _cart_id(user_id)
    _ensure_cart_doc(uid)
    get_carts_collection().update_one(
        {"user_id": uid},
        {"$set": {"items": [], "updated_at": now_utc()}},
    )
    return build_cart_payload(uid)


def merge_cart_items(user_id: Any, items: Any) -> dict:
    """Merge a guest (pre-login) cart into the authenticated user's cart.

    Every incoming line is re-resolved against the products collection and
    re-clamped to stock, so a tampered localStorage payload can only ever
    add real, available products - never prices.
    """
    uid = _cart_id(user_id)
    if not isinstance(items, (list, tuple)):
        return build_cart_payload(uid)

    for entry in items:
        if not isinstance(entry, dict):
            continue
        pid = entry.get("product_id") or entry.get("id")
        if not pid:
            continue
        try:
            qty = int(entry.get("quantity", 1) or 1)
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        try:
            data = product_to_dict(get_product(pid))
        except ProductNotFoundError:
            continue
        stock = data["stock_quantity"]
        if stock <= 0:
            continue
        line = _find_cart_line(uid, data["id"])
        existing = _to_int(line.get("quantity"), 0) if line else 0
        wanted = min(existing + qty, stock, MAX_CART_QUANTITY)
        if wanted <= 0:
            continue
        try:
            set_cart_quantity(uid, data["id"], wanted)
        except MarketError:
            continue

    return build_cart_payload(uid)


def cart_item_count(user_id: Any) -> int:
    """Total units in the cart - used for the navbar badge.

    Never raises: an unreachable database or empty cart simply yields 0 so
    the shared navbar can always render.
    """
    try:
        return int(build_cart_payload(user_id).get("item_count", 0))
    except (MarketError, MongoUnavailableError):
        return 0