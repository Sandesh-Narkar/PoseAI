"""Fitness Market — business logic.

Workout analytics, game data and commerce data are separate sources of
truth: this module ONLY reads/writes the products/categories/carts
collections and never touches users/workout/game collections.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import Any

from . import repository, schemas, validators
from .errors import (
    InsufficientStockError,
    OrderNotFoundError,
    OutOfStockError,
    ProductInactiveError,
    ProductNotFoundError,
    ValidationError,
)
from .validators import parse_price, parse_product_id

_CURRENCY = "INR"
FREE_DELIVERY_THRESHOLD = 999
DELIVERY_FEE = 99

# ==============================================================================
# SHOP-BY-GOAL MAPPING
# ==============================================================================
# Goals are honest catalogs derived from product tags — nothing fake, and the
# same mapping powers the landing "SHOP BY GOAL" cards, the products page
# `goal=` filter, and goal-aware recommendations.

GOALS = [
    {
        "key": "build-muscle",
        "label": "Build Muscle",
        "description": "Proteins, gainers and mass builders.",
        "icon": "fitness_center",
        "tags": ["protein", "gainer", "isolate", "concentrate", "casein"],
    },
    {
        "key": "lose-weight",
        "label": "Lose Weight",
        "description": "Lean protein, EAAs and hydration helpers.",
        "icon": "monitor_weight",
        "tags": ["protein", "bcaa", "eaa", "electrolytes", "greens"],
    },
    {
        "key": "strength",
        "label": "Increase Strength",
        "description": "Creatine, pre-workout and focus aids.",
        "icon": "fitness_center",
        "tags": ["creatine", "pre-workout", "caffeine", "citrulline"],
    },
    {
        "key": "recovery",
        "label": "Improve Recovery",
        "description": "Aminos, sleep and mobility support.",
        "icon": "bedtime",
        "tags": ["recovery", "sleep", "electrolytes", "collagen", "magnesium"],
    },
    {
        "key": "wellness",
        "label": "Daily Wellness",
        "description": "Multivitamins and everyday health staples.",
        "icon": "spa",
        "tags": ["multivitamin", "vitamin-d", "omega-3", "probiotic", "ashwagandha"],
    },
]

GOAL_TAG_MAP: dict[str, list[str]] = {goal["key"]: goal["tags"] for goal in GOALS}

# Profile `fitness_goal` values -> market goal keys (recommendations).
USER_GOAL_TO_GOAL_KEY: dict[str, str] = {
    "lose weight": "lose-weight",
    "maintain weight": "wellness",
    "gain weight": "build-muscle",
    "improve strength": "strength",
    "improve mobility": "recovery",
    "improve general fitness": "wellness",
}


# ==============================================================================
# CATALOG
# ==============================================================================

def categories() -> list[dict[str, Any]]:
    repository._ready()
    cats = repository.list_categories()
    products_col = repository.get_products_collection()

    counts: dict[str, int] = {}
    try:
        pipeline = [
            {"$match": {"is_active": True}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        ]
        for item in products_col.aggregate(pipeline):
            if item.get("_id"):
                counts[str(item["_id"])] = int(item.get("count", 0))
        counts["deals"] = int(products_col.count_documents({"is_active": True, "is_deal": True}))
        counts["creatine"] = int(products_col.count_documents({
            "is_active": True,
            "$or": [{"category": "creatine"}, {"subcategory": "creatine"}, {"tags": "creatine"}],
        }))
        counts["vitamins"] = int(products_col.count_documents({
            "is_active": True,
            "$or": [{"category": "vitamins"}, {"subcategory": "vitamins"}, {"tags": "vitamins"}],
        }))
    except Exception:
        counts = {}

    result = []
    for doc in cats:
        slug = str(doc.get("slug") or "")
        enriched = dict(doc)
        enriched["product_count"] = counts.get(slug, 0)
        result.append(schemas.category_dto(enriched))
    return result


def build_product_query(params: dict[str, Any]) -> dict[str, Any]:
    """Translate validated UI filters into a single Mongo query dict.

    Supports single or multiple categories via comma-separated string or list.
    `category=deals` is a virtual rail that maps to the `is_deal` flag so
    deal products keep their real category while still feeding the Deals
    rail.
    """
    and_clauses: list[dict[str, Any]] = [{"is_active": True}]

    # Extract categories (support list or comma-separated string or both)
    raw_cats = []
    if params.get("categories"):
        cats_val = params.get("categories")
        if isinstance(cats_val, list):
            raw_cats.extend(cats_val)
        elif isinstance(cats_val, str):
            raw_cats.extend([c.strip() for c in cats_val.split(",") if c.strip()])
    if params.get("category"):
        cat_val = params.get("category")
        if isinstance(cat_val, list):
            raw_cats.extend(cat_val)
        elif isinstance(cat_val, str):
            raw_cats.extend([c.strip() for c in cat_val.split(",") if c.strip()])

    if raw_cats:
        has_deals = any(c.lower() == "deals" for c in raw_cats)
        other_cats = [c for c in raw_cats if c.lower() != "deals"]

        cat_or_clauses: list[dict[str, Any]] = []
        if has_deals:
            cat_or_clauses.append({"is_deal": True})

        if other_cats:
            slug_set = set()
            for c in other_cats:
                s = _normalize_slug(c)
                if s:
                    slug_set.add(s)
                    slug_set.add(s.replace("-", "_"))
                    slug_set.add(s.replace("_", "-"))

            sub_rails = {"creatine", "vitamins"} & slug_set
            primary_cats = slug_set - sub_rails

            if primary_cats:
                cat_or_clauses.append({"category": {"$in": list(primary_cats)}})
            if sub_rails:
                cat_or_clauses.append({"subcategory": {"$in": list(sub_rails)}})
                cat_or_clauses.append({"tags": {"$in": list(sub_rails)}})

        if cat_or_clauses:
            if len(cat_or_clauses) == 1:
                and_clauses.append(cat_or_clauses[0])
            else:
                and_clauses.append({"$or": cat_or_clauses})

    subcategory = params.get("subcategory")
    if subcategory:
        and_clauses.append({"subcategory": _normalize_slug(subcategory)})

    search = params.get("search")
    if search:
        search_terms = [search.strip()]
        lower_term = search.lower().strip()
        if "protien" in lower_term:
            search_terms.append(lower_term.replace("protien", "protein"))
        elif "protein" in lower_term:
            search_terms.append(lower_term.replace("protein", "protien"))
        pattern = "|".join(re.escape(t) for t in search_terms if t)
        and_clauses.append({
            "$or": [
                {"name": {"$regex": pattern, "$options": "i"}},
                {"brand": {"$regex": pattern, "$options": "i"}},
                {"category": {"$regex": pattern, "$options": "i"}},
                {"tags": {"$regex": pattern, "$options": "i"}},
            ]
        })

    brands = params.get("brands") or []
    if brands:
        and_clauses.append({"brand": {"$in": brands}})

    price_range: dict[str, Any] = {}
    if params.get("min_price") is not None:
        price_range["$gte"] = params["min_price"]
    if params.get("max_price") is not None:
        price_range["$lte"] = params["max_price"]
    if price_range:
        and_clauses.append({"price": price_range})

    if params.get("in_stock"):
        and_clauses.append({"stock_quantity": {"$gt": 0}})

    if params.get("rating") is not None:
        and_clauses.append({"rating": {"$gte": params["rating"]}})

    discount = params.get("discount")
    if discount is not None:
        and_clauses.append({"discount_percentage": {"$gte": discount}})

    if params.get("is_deal") and not raw_cats:
        and_clauses.append({"is_deal": True})

    goal = params.get("goal")
    if goal:
        goal_tags = GOAL_TAG_MAP.get(goal)
        if goal_tags:
            and_clauses.append({"tags": {"$in": goal_tags}})

    if len(and_clauses) == 1:
        return and_clauses[0]
    return {"$and": and_clauses}


def build_sort(sort_key: str) -> list[tuple[str, int]]:
    if sort_key == "price_asc":
        return [("price", 1), ("_id", 1)]
    if sort_key == "price_desc":
        return [("price", -1), ("_id", 1)]
    if sort_key == "popularity":
        return [("review_count", -1), ("rating", -1), ("_id", 1)]
    if sort_key == "rating_desc":
        return [("rating", -1), ("review_count", -1), ("_id", 1)]
    if sort_key == "discount_desc":
        return [("discount_percentage", -1), ("price", 1), ("_id", 1)]
    if sort_key == "newest":
        return [("created_at", -1), ("_id", 1)]
    return [("is_deal", -1), ("rating", -1), ("review_count", -1), ("_id", 1)]


def _normalize_slug(value: str) -> str:
    value = value.strip().lower().replace("&", "and")
    return re.sub(r"[^a-z0-9-]+", "-", value).strip("-")


def browse(
    params: dict[str, Any], favorite_ids: set[str] | None = None
) -> dict[str, Any]:
    """Full listing search: search/filter/sort/paginate in one pass.

    `favorite_ids` (the current user's favorite-id set) lets each card carry
    its persisted `is_favorite` flag without a second round trip.
    """
    query = build_product_query(params)
    sort = build_sort(params.get("sort", "recommended"))
    page = params.get("page")
    limit = params.get("limit")
    docs, total, total_pages = repository.list_products(
        query=query, sort=sort, page=page, limit=limit
    )
    items = [
        schemas.product_dto(doc, is_favorite=str(doc["_id"]) in (favorite_ids or set()))
        for doc in docs
    ]
    return {
        "products": items,
        "items": items,
        "total": total,
        "has_more": (page * limit) < total,
        "pagination": {
            "page": params.get("page", validators.DEFAULT_PAGE),
            "limit": params.get("limit", validators.DEFAULT_PAGE_SIZE),
            "total": total,
            "total_pages": total_pages,
        },
    }


def product_detail(
    product_id: Any, favorite_ids: set[str] | None = None
) -> dict[str, Any]:
    oid = parse_product_id(product_id)
    doc = repository.find_product_by_id(oid)
    if doc is None:
        raise ProductNotFoundError("The requested product does not exist.")
    if not doc.get("is_active", True):
        raise ProductInactiveError("This product is no longer available.")
    return schemas.product_dto(doc, is_favorite=str(oid) in (favorite_ids or set()))


def related_products(
    product_id: Any,
    category: str | None,
    count: int = 4,
    favorite_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    oid = parse_product_id(product_id)
    query: dict[str, Any] = {"is_active": True, "_id": {"$ne": oid}}
    if category:
        query["category"] = category
    docs, _, _ = repository.list_products(query=query, sort=[("rating", -1), ("_id", 1)], page=1, limit=count)
    return [
        schemas.product_dto(doc, is_favorite=str(doc["_id"]) in (favorite_ids or set()))
        for doc in docs
    ]


# ==============================================================================
# LANDING / HOME
# ==============================================================================

_HOME_SECTION_LIMIT = 8


def _sample_product(query: dict[str, Any]) -> dict[str, Any] | None:
    repository._ready()
    docs, _, _ = repository.list_products(
        query=query, sort=[("rating", -1), ("review_count", -1), ("_id", 1)], page=1, limit=1
    )
    return docs[0] if docs else None


def _first_image(product: dict[str, Any] | None) -> str:
    if not product:
        return ""
    images = product.get("image_urls") or []
    return images[0] if isinstance(images, list) and images else ""


def _section(
    query: dict[str, Any], sort: list[tuple[str, int]], favorite_ids: set[str], limit: int = _HOME_SECTION_LIMIT
) -> list[dict[str, Any]]:
    docs, _, _ = repository.list_products(query=query, sort=sort, page=1, limit=limit)
    return [
        schemas.product_dto(doc, is_favorite=str(doc["_id"]) in favorite_ids)
        for doc in docs
    ]


def _category_stats() -> list[dict[str, Any]]:
    """Active categories with live product counts and a representative image."""
    repository._ready()
    stats: list[dict[str, Any]] = []
    for doc in repository.list_categories():
        slug = doc.get("slug", "")
        query: dict[str, Any] = {"is_active": True}
        if slug == "deals":
            query["is_deal"] = True
        else:
            query["category"] = slug
        count = repository.get_products_collection().count_documents(query)
        item = schemas.category_dto(doc)
        item["count"] = count
        item["image"] = _first_image(_sample_product(query))
        stats.append(item)
    return stats


def _goal_stats() -> list[dict[str, Any]]:
    repository._ready()
    stats: list[dict[str, Any]] = []
    for goal in GOALS:
        query: dict[str, Any] = {"is_active": True, "tags": {"$in": goal["tags"]}}
        count = repository.get_products_collection().count_documents(query)
        stats.append({**goal, "count": count, "image": _first_image(_sample_product(query))})
    return stats


def home(user_id: str, fitness_goal: str = "") -> dict[str, Any]:
    """Everything the landing page needs in one authenticated request.

    Recommendations are *grounded* in the user's stored profile goal whenever
    one is set; otherwise they fall back to the catalog's best sellers. No
    fake AI claims — the section explicitly says which basis was used.
    """
    favorite_ids = repository.favorite_id_set(user_id)

    deals = _section(
        {"is_active": True, "is_deal": True},
        build_sort("discount_desc"),
        favorite_ids,
    )
    best_sellers = _section(
        {"is_active": True},
        [("review_count", -1), ("rating", -1), ("_id", 1)],
        favorite_ids,
    )
    new_arrivals = _section(
        {"is_active": True},
        build_sort("newest"),
        favorite_ids,
    )
    essentials = _section(
        {"is_active": True, "category": "accessories"},
        [("rating", -1), ("review_count", -1), ("_id", 1)],
        favorite_ids,
    )

    goal_key = USER_GOAL_TO_GOAL_KEY.get(fitness_goal.strip().lower(), "")
    if goal_key:
        goal = next(g for g in GOALS if g["key"] == goal_key)
        recommended = _section(
            {"is_active": True, "tags": {"$in": goal["tags"]}},
            [("review_count", -1), ("rating", -1), ("_id", 1)],
            favorite_ids,
        )
        recommended_block = {
            "title": "Recommended for your training",
            "subtitle": "Based on your profile goal — {0}.".format(goal["label"]),
            "basis": "profile-goal",
            "goal_key": goal_key,
            "items": recommended,
        }
    else:
        recommended_block = {
            "title": "Recommended for your training",
            "subtitle": "Top products by popularity across the catalog.",
            "basis": "best-sellers",
            "goal_key": "",
            "items": best_sellers,
        }

    return {
        "home": {
            "categories": _category_stats(),
            "goals": _goal_stats(),
            "deals": deals,
            "best_sellers": best_sellers,
            "new_arrivals": new_arrivals,
            "essentials": essentials,
            "recommended": recommended_block,
        }
    }


# ==============================================================================
# CART
# ==============================================================================

def _hydrate_line(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Turn a raw cart line (product_id + quantity) into a priced line."""
    try:
        product = repository.find_product_by_id(entry["product_id"])
    except Exception:
        return None
    if product is None:
        return None
    dto = schemas.product_dto(product)
    quantity = int(entry.get("quantity") or 1)
    available = dto["is_active"] and dto["stock_quantity"] > 0

    line: dict[str, Any] = {
        "product_id": dto["id"],
        "name": dto["name"],
        "brand": dto["brand"],
        "category": dto["category"],
        "image_url": dto["image"],
        "price": dto["price"],
        "original_price": dto["original_price"],
        "discount_percentage": dto["discount_percentage"],
        "quantity": quantity,
        "max_quantity": dto["stock_quantity"],
        "in_stock": available,
        "stock_label": dto["stock_label"],
        "line_mrp": 0,
        "line_discount": 0,
        "line_total": 0,
        "clamped_to_stock": False,
    }

    if not available:
        return line

    effective_qty = min(quantity, dto["stock_quantity"])
    if effective_qty < quantity:
        line["clamped_to_stock"] = True
    line["quantity"] = effective_qty
    line["line_mrp"] = dto["original_price"] * effective_qty
    line["line_discount"] = (dto["original_price"] - dto["price"]) * effective_qty
    line["line_total"] = dto["price"] * effective_qty
    return line


def cart_payload(user_id: str) -> dict[str, Any]:
    """Re-derive ALL cart money from live catalog prices (server-authoritative).

    `total` is the price of goods (kept for backwards compatibility), while
    `delivery_fee`/`grand_total` reflect the shipping policy: delivery is
    free at/above the threshold, otherwise a flat fee.
    """
    doc = repository.get_cart_doc(user_id)
    raw_lines = (doc or {}).get("items") or []

    items: list[dict[str, Any]] = []
    subtotal = 0
    discount = 0
    total = 0
    item_count = 0
    for entry in raw_lines:
        line = _hydrate_line(entry)
        if line is None:
            continue
        if line["in_stock"]:
            subtotal += line["line_mrp"]
            discount += line["line_discount"]
            total += line["line_total"]
            item_count += line["quantity"]
        items.append(line)

    delivery_fee = 0 if item_count == 0 or total >= FREE_DELIVERY_THRESHOLD else DELIVERY_FEE

    return {
        "cart_money_total": total,
        "item_count": item_count,
        "currency": _CURRENCY,
        "items": items,
        "subtotal": subtotal,
        "discount": discount,
        "delivery_fee": delivery_fee,
        "total": total,
        "grand_total": total + delivery_fee,
        "free_delivery_threshold": FREE_DELIVERY_THRESHOLD,
        "updated_at": (doc or {}).get("updated_at"),
    }


def cart_count(user_id: str) -> int:
    doc = repository.get_cart_doc(user_id)
    return sum(int(item.get("quantity") or 0) for item in ((doc or {}).get("items") or []))


def _check_cart_operation(product_id: Any, quantity: int) -> str:
    """Shared stock/enablement gate for every cart mutation."""
    oid = parse_product_id(product_id)
    product = repository.find_product_by_id(oid)
    if product is None:
        raise ProductNotFoundError("The requested product does not exist.")
    if not product.get("is_active", True):
        raise ProductInactiveError("This product is no longer available.")
    stock = int(product.get("stock_quantity") or 0)
    if stock <= 0:
        raise OutOfStockError("Sorry, this item is out of stock.")
    if quantity > stock:
        raise InsufficientStockError(
            "Only {0} unit(s) of this item are left in stock.".format(stock),
            available_quantity=stock,
        )
    return str(oid)


def add_to_cart(user_id: str, product_id: Any, quantity: int) -> dict[str, Any]:
    _check_cart_operation(product_id, quantity)
    repository.set_cart_quantity(user_id, product_id, quantity)
    return cart_payload(user_id)


def update_quantity(user_id: str, product_id: Any, quantity: int) -> dict[str, Any]:
    _check_cart_operation(product_id, quantity)
    repository.set_cart_quantity(user_id, product_id, quantity)
    return cart_payload(user_id)


def remove_item(user_id: str, product_id: Any) -> dict[str, Any]:
    repository.remove_cart_item(user_id, product_id)
    return cart_payload(user_id)


def clear(user_id: str) -> dict[str, Any]:
    repository.clear_cart(user_id)
    return cart_payload(user_id)


# ==============================================================================
# FILTER FACETS (brands for the filter panel)
# ==============================================================================

def brands() -> list[str]:
    import pymongo

    repository._ready()
    try:
        result = repository.get_products_collection().distinct("brand", {"is_active": True})
    except Exception:
        return []
    return sorted(str(b) for b in result if isinstance(b, (str, int, float)))


# ==============================================================================
# FAVORITES
# ==============================================================================

def favorite_ids(user_id: str) -> set[str]:
    return repository.favorite_id_set(user_id)


def favorites(user_id: str) -> dict[str, Any]:
    """Hydrate a user's favorites into full product DTOs (active ones only).

    Re-verifies the catalog at read time so a product that was later made
    inactive simply disappears from the list rather than surfacing broken
    data.
    """
    products: list[dict[str, Any]] = []
    for pid_str in repository.favorite_product_ids(user_id):
        try:
            doc = repository.find_product_by_id(pid_str)
        except Exception:
            continue
        if doc is None or not doc.get("is_active", True):
            continue
        products.append(
            schemas.product_dto(doc, is_favorite=True)
        )
    return {"products": products, "items": products, "count": len(products)}


def add_favorite(user_id: str, product_id: Any) -> dict[str, Any]:
    oid = parse_product_id(product_id)
    doc = repository.find_product_by_id(oid)
    if doc is None:
        raise ProductNotFoundError("The requested product does not exist.")
    if not doc.get("is_active", True):
        raise ProductInactiveError("This product is no longer available.")
    repository.add_favorite(user_id, oid)
    return {
        "product_id": str(oid),
        "favorited": True,
        "count": repository.count_favorites(user_id),
    }


def remove_favorite(user_id: str, product_id: Any) -> dict[str, Any]:
    oid = parse_product_id(product_id)
    repository.remove_favorite(user_id, oid)
    return {
        "product_id": str(oid),
        "favorited": False,
        "count": repository.count_favorites(user_id),
    }


# ==============================================================================
# ORDERS
# ==============================================================================

# Fields snapshotted from a hydrated cart line when an order is placed.
_ORDER_LINE_FIELDS = (
    "product_id",
    "name",
    "brand",
    "category",
    "image_url",
    "price",
    "original_price",
    "discount_percentage",
    "quantity",
    "line_mrp",
    "line_discount",
    "line_total",
)


def create_order(user_id: str, address: dict[str, str]) -> dict[str, Any]:
    """Convert the current cart into a persistent order and clear the cart.

    Payment is intentionally NOT collected here: `payment_status` is written
    as PENDING and the order is never presented as paid. Totals are taken
    from the server-authoritative cart payload, never from the client.
    """
    payload = cart_payload(user_id)
    if payload["item_count"] <= 0:
        raise ValidationError("Your cart is empty — add products before placing an order.")

    items = []
    for line in payload["items"]:
        if not line["in_stock"]:
            continue
        items.append({field: line.get(field) for field in _ORDER_LINE_FIELDS})

    now = datetime.now(timezone.utc)
    order_number = "POM-{0}-{1}".format(now.strftime("%Y%m%d"), secrets.token_hex(3).upper())

    order = {
        "user_id": str(user_id),
        "order_number": order_number,
        "items": items,
        "item_count": sum(int(item.get("quantity") or 0) for item in items),
        "subtotal": payload["subtotal"],
        "discount": payload["discount"],
        "delivery_fee": payload["delivery_fee"],
        "total": payload["grand_total"],
        "currency": payload["currency"],
        "shipping_address": address,
        "status": "PENDING",
        "status_label": "Pending",
        "payment_status": "PENDING",
        "payment_label": "Payment gateway integration pending — no amount has been charged.",
        "created_at": now,
        "updated_at": now,
    }
    repository.insert_order(order)
    repository.clear_cart(user_id)
    return schemas.order_dto(order)


def orders(user_id: str) -> dict[str, Any]:
    result = [schemas.order_dto(order) for order in repository.list_orders(user_id)]
    return {"orders": result, "count": len(result)}


def order_detail(user_id: str, order_id: Any) -> dict[str, Any]:
    oid = parse_product_id(order_id)
    doc = repository.find_order(user_id, oid)
    if doc is None:
        raise OrderNotFoundError("Order not found.")
    return schemas.order_dto(doc)


def record_recently_viewed(user_id: str, product_id: Any) -> None:
    repository.record_recently_viewed(user_id, product_id)


def recently_viewed(user_id: str, limit: int = 8, favorite_ids: set[str] | None = None) -> dict[str, Any]:
    docs = repository.list_recently_viewed(user_id, limit=limit)
    fav_set = favorite_ids or set()
    items = [schemas.product_card_dto(doc, is_favorite=(str(doc["_id"]) in fav_set)) for doc in docs]
    return {"products": items, "items": items, "count": len(items)}