"""Fitness Market — MongoDB access layer.

Collections (within the shared `poseai` database / mock fallback):

    products    — catalog items; int price/original_price/discount_percentage,
                  image_urls array, unique slug, rating, review_count,
                  stock_quantity, is_active, created_at/updated_at.
    categories  — catalog taxonomy; name, unique slug, parent_category_id,
                  sort_order, is_active.
    carts       — one document per user (user_id unique); items are
                  [{product_id, quantity}] only — price is NEVER stored in a
                  cart. All cart money is re-derived from live catalog data
                  at read time (server-authoritative totals).

Cart product_ids are stored as ObjectId-hex *strings* (the same convention
the rest of the app uses for `session["user_id"]`), which reads cleanly and
stays trivially JSON-serializable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .validators import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE,
    MAX_PAGE_SIZE,
    parse_product_id,
)

PRODUCTS_COLLECTION = "products"
CATEGORIES_COLLECTION = "categories"
CARTS_COLLECTION = "carts"
FAVORITES_COLLECTION = "favorites"
ORDERS_COLLECTION = "orders"

_INSTALLED = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_products_collection():
    from database.mongo import get_db

    return get_db()[PRODUCTS_COLLECTION]


def get_categories_collection():
    from database.mongo import get_db

    return get_db()[CATEGORIES_COLLECTION]


def get_carts_collection():
    from database.mongo import get_db

    return get_db()[CARTS_COLLECTION]


def get_favorites_collection():
    from database.mongo import get_db

    return get_db()[FAVORITES_COLLECTION]


def get_orders_collection():
    from database.mongo import get_db

    return get_db()[ORDERS_COLLECTION]


def ensure_indexes() -> None:
    """Idempotent index setup; safe against both PyMongo and mongomock."""
    global _INSTALLED
    products = get_products_collection()
    products.create_index([("slug", 1)], unique=True, name="uix_products_slug")
    products.create_index([("is_active", 1), ("category", 1), ("created_at", -1)], name="idx_products_active_category")
    products.create_index([("is_active", 1), ("price", 1)], name="idx_products_active_price")
    products.create_index([("is_active", 1), ("rating", -1)], name="idx_products_active_rating")
    categories = get_categories_collection()
    categories.create_index([("slug", 1)], unique=True, name="uix_categories_slug")
    carts = get_carts_collection()
    carts.create_index([("user_id", 1)], unique=True, name="uix_carts_user")
    favorites = get_favorites_collection()
    favorites.create_index(
        [("user_id", 1), ("product_id", 1)],
        unique=True,
        name="uix_favorites_user_product",
    )
    favorites.create_index([("user_id", 1), ("created_at", -1)], name="idx_favorites_user_created")
    orders = get_orders_collection()
    orders.create_index([("user_id", 1), ("created_at", -1)], name="idx_orders_user_created")
    orders.create_index([("order_number", 1)], unique=True, name="uix_orders_number")
    _INSTALLED = True


def _ready() -> None:
    if not _INSTALLED:
        ensure_indexes()


# ==============================================================================
# CATEGORIES
# ==============================================================================

def list_categories(*, include_inactive: bool = False) -> list[dict[str, Any]]:
    _ready()
    query: dict[str, Any] = {}
    if not include_inactive:
        query["is_active"] = True
    return list(
        get_categories_collection().find(query).sort([("sort_order", 1), ("name", 1)])
    )


def find_category_by_slug(slug: str) -> dict[str, Any] | None:
    _ready()
    return get_categories_collection().find_one({"slug": slug})


# ==============================================================================
# PRODUCTS
# ==============================================================================

def find_product_by_id(product_id: Any) -> dict[str, Any] | None:
    """Fetch a product by ObjectId regardless of active state (cart hydration)."""
    _ready()
    oid = parse_product_id(product_id)
    return get_products_collection().find_one({"_id": oid})


def find_product_by_slug(slug: str) -> dict[str, Any] | None:
    _ready()
    return get_products_collection().find_one({"slug": slug})


def list_products(
    *,
    query: dict[str, Any],
    sort: list[tuple[str, int]],
    page: int = DEFAULT_PAGE,
    limit: int = DEFAULT_PAGE_SIZE,
) -> tuple[list[dict[str, Any]], int, int]:
    """Return (docs, total, total_pages) for an already-built Mongo query."""
    _ready()
    collection = get_products_collection()
    safe_page = min(max(page, 1), MAX_PAGE)
    safe_limit = min(max(int(limit or DEFAULT_PAGE_SIZE), 1), MAX_PAGE_SIZE)
    total = collection.count_documents(query)
    total_pages = max(1, _ceil(total / safe_limit)) if total else 0
    cursor = (
        collection.find(query)
        .sort(sort)
        .skip((safe_page - 1) * safe_limit)
        .limit(safe_limit)
    )
    return list(cursor), total, total_pages


def _ceil(value: float) -> int:
    import math

    return int(math.ceil(value))


# ==============================================================================
# CARTS
# ==============================================================================

def get_cart_doc(user_id: str) -> dict[str, Any] | None:
    _ready()
    return get_carts_collection().find_one({"user_id": str(user_id)})


def set_cart_quantity(user_id: str, product_id: Any, quantity: int) -> None:
    """Insert/update one cart line with an explicit quantity (server checked)."""
    _ready()
    oid = parse_product_id(product_id)
    pid_str = str(oid)
    collection = get_carts_collection()
    now = _now()
    existing = collection.find_one({"user_id": str(user_id)})

    if existing is None:
        collection.insert_one(
            {
                "user_id": str(user_id),
                "items": [{"product_id": pid_str, "quantity": quantity}],
                "created_at": now,
                "updated_at": now,
            }
        )
        return

    items = existing.get("items") or []
    replaced = False
    for line in items:
        if str(line.get("product_id")) == pid_str:
            line["quantity"] = quantity
            replaced = True
            break
    if replaced:
        collection.update_one(
            {"user_id": str(user_id)}, {"$set": {"items": items, "updated_at": now}}
        )
    else:
        collection.update_one(
            {"user_id": str(user_id)},
            {
                "$push": {"items": {"product_id": pid_str, "quantity": quantity}},
                "$set": {"updated_at": now},
            },
        )


def remove_cart_item(user_id: str, product_id: Any) -> None:
    _ready()
    oid = parse_product_id(product_id)
    get_carts_collection().update_one(
        {"user_id": str(user_id)},
        {
            "$pull": {"items": {"product_id": str(oid)}},
            "$set": {"updated_at": _now()},
        },
    )


def clear_cart(user_id: str) -> None:
    _ready()
    get_carts_collection().update_one(
        {"user_id": str(user_id)},
        {"$set": {"items": [], "updated_at": _now()}},
        upsert=True,
    )


# ==============================================================================
# FAVORITES
# ==============================================================================

def favorite_id_set(user_id: str) -> set[str]:
    """Set of favorited product-id hex strings for the current user."""
    _ready()
    return {
        str(doc.get("product_id"))
        for doc in get_favorites_collection().find(
            {"user_id": str(user_id)}, {"product_id": 1, "_id": 0}
        )
    }


def favorite_product_ids(user_id: str) -> list[str]:
    """Favorite product ids, newest first (stable for hydration + counts)."""
    _ready()
    cursor = (
        get_favorites_collection()
        .find({"user_id": str(user_id)}, {"product_id": 1, "_id": 0})
        .sort([("created_at", -1), ("_id", -1)])
    )
    return [str(doc["product_id"]) for doc in cursor]


def add_favorite(user_id: str, product_id: Any) -> bool:
    """Record a favorite; returns True if newly added (False if already there)."""
    _ready()
    oid = parse_product_id(product_id)
    pid_str = str(oid)
    collection = get_favorites_collection()
    existing = collection.find_one(
        {"user_id": str(user_id), "product_id": pid_str}, {"_id": 1}
    )
    if existing is not None:
        return False
    collection.insert_one(
        {"user_id": str(user_id), "product_id": pid_str, "created_at": _now()}
    )
    return True


def remove_favorite(user_id: str, product_id: Any) -> bool:
    """Remove a favorite; returns True if a document was removed."""
    _ready()
    oid = parse_product_id(product_id)
    result = get_favorites_collection().delete_one(
        {"user_id": str(user_id), "product_id": str(oid)}
    )
    return bool(result.deleted_count)


def count_favorites(user_id: str) -> int:
    _ready()
    return get_favorites_collection().count_documents({"user_id": str(user_id)})


# ==============================================================================
# ORDERS
# ==============================================================================

def insert_order(document: dict[str, Any]) -> None:
    _ready()
    get_orders_collection().insert_one(document)


def list_orders(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    _ready()
    safe_limit = min(max(int(limit or 50), 1), 100)
    cursor = (
        get_orders_collection()
        .find({"user_id": str(user_id)})
        .sort([("created_at", -1), ("_id", -1)])
        .limit(safe_limit)
    )
    return list(cursor)


def find_order(user_id: str, order_id: Any) -> dict[str, Any] | None:
    """Fetch an order by id — scoped to the authenticated user."""
    _ready()
    oid = parse_product_id(order_id, field="order_id")
    return get_orders_collection().find_one({"user_id": str(user_id), "_id": oid})


# ==============================================================================
# RECENTLY VIEWED
# ==============================================================================

def get_recently_viewed_collection():
    from database.mongo import get_db

    return get_db()["recently_viewed"]


def record_recently_viewed(user_id: str, product_id: Any) -> None:
    """Track viewed product per authenticated user, maintaining latest first."""
    _ready()
    oid = parse_product_id(product_id)
    pid_str = str(oid)
    col = get_recently_viewed_collection()
    now = _now()
    col.update_one(
        {"user_id": str(user_id)},
        {"$pull": {"product_ids": pid_str}},
        upsert=True,
    )
    col.update_one(
        {"user_id": str(user_id)},
        {
            "$push": {
                "product_ids": {
                    "$each": [pid_str],
                    "$position": 0,
                    "$slice": 12,
                }
            },
            "$set": {"updated_at": now},
        },
        upsert=True,
    )


def list_recently_viewed(user_id: str, limit: int = 8) -> list[dict[str, Any]]:
    """Return active product documents viewed recently by this user."""
    _ready()
    col = get_recently_viewed_collection()
    doc = col.find_one({"user_id": str(user_id)})
    if not doc:
        return []
    pids = (doc.get("product_ids") or [])[:limit]
    if not pids:
        return []
    from bson import ObjectId

    oids = []
    for pid in pids:
        try:
            oids.append(ObjectId(pid))
        except Exception:
            pass
    if not oids:
        return []
    prods = {
        str(p["_id"]): p
        for p in get_products_collection().find({"_id": {"$in": oids}, "is_active": True})
    }
    return [prods[pid] for pid in pids if pid in prods]