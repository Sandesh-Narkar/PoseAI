"""Fitness Market — response DTOs (pure functions, schema owned here).

Cart money fields carry the `cart_money_*` prefix to keep one obvious
source of truth even after an `orders` collection is introduced later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# Cart documents are hydrated by the service layer — this module never
# talks to MongoDB. It only shapes already-validated documents.
CART_MONEY_CONTRACT = ("currency", "subtotal", "discount", "total", "item_count")


def _iso(dt: Any) -> str | None:
    if isinstance(dt, datetime):
        return dt.isoformat()
    if isinstance(dt, str):
        return dt
    return None


def product_dto(product: dict[str, Any], is_favorite: bool = False) -> dict[str, Any]:
    """Public shape of a product; one-to-one with the products collection."""
    price = int(product.get("price") or 0)
    original_price = int(product.get("original_price") or price)
    discount = max(0, original_price - price)
    discount_percentage = int(product.get("discount_percentage") or 0)
    if original_price > 0:
        discount_percentage = round((discount / original_price) * 100)
    stock = int(product.get("stock_quantity") or 0)
    rating = float(product.get("rating") or 0.0)
    review_count = int(product.get("review_count") or 0)

    images = product.get("image_urls") or []
    if not isinstance(images, list):
        images = [images] if isinstance(images, str) else []

    return {
        "id": str(product.get("_id")),
        "slug": product.get("slug", ""),
        "name": product.get("name", ""),
        "brand": product.get("brand", ""),
        "category": product.get("category", ""),
        "subcategory": product.get("subcategory", ""),
        "description": product.get("description", ""),
        "price": price,
        "original_price": original_price,
        "discount_percentage": discount_percentage,
        "image_urls": images,
        "image": images[0] if images else "",
        "tags": product.get("tags") or [],
        "rating": rating,
        "review_count": review_count,
        "stock_quantity": stock,
        "in_stock": stock > 0 and bool(product.get("is_active", True)),
        "stock_label": stock_label(stock),
        "is_active": bool(product.get("is_active", True)),
        "is_deal": bool(product.get("is_deal", False)),
        "is_favorite": bool(is_favorite),
        "badge": product.get("badge") or "",
        "badge_color": product.get("badge_color") or "",
        "weight_label": product.get("weight_label") or "",
        "ai_match": product.get("ai_match") or None,
        "product_type": product.get("product_type") or "general",
        "flavor_options": product.get("flavor_options") or [],
        "size_options": product.get("size_options") or [],
        "weight_options": product.get("weight_options") or [],
        "variants": product.get("variants") or [],
        "specifications": product.get("specifications") or {},
        "nutrition_facts": product.get("nutrition_facts") or [],
        "highlights": product.get("highlights") or [],
        "synergy_stack": product.get("synergy_stack") or [],
        "target_benefit": product.get("target_benefit") or "",
        "benefits": product.get("benefits") or [],
        "usage": product.get("usage") or "",
        "ingredients": product.get("ingredients") or [],
        "created_at": _iso(product.get("created_at")),
        "updated_at": _iso(product.get("updated_at")),
    }


# Presentational alias for product card DTOs
product_card_dto = product_dto


def stock_label(stock: int) -> str:
    if stock <= 0:
        return "Out of Stock"
    if stock <= 5:
        return "Only {0} left".format(stock)
    return "In Stock"


def category_dto(category: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(category.get("_id")),
        "slug": category.get("slug", ""),
        "name": category.get("name", ""),
        "subtitle": category.get("subtitle", ""),
        "product_count": int(category.get("product_count") or 0),
        "parent_category_id": str(category["parent_category_id"]) if category.get("parent_category_id") else None,
        "sort_order": int(category.get("sort_order") or 0),
        "is_active": bool(category.get("is_active", True)),
    }


def order_dto(order: dict[str, Any]) -> dict[str, Any]:
    """Public shape of an order (user-scoped; item snapshots stored on create)."""
    items = order.get("items") or []
    item_count = int(order.get("item_count") or sum(int(i.get("quantity") or 0) for i in items))
    return {
        "id": str(order.get("_id")),
        "order_id": str(order.get("_id")),
        "order_number": order.get("order_number", ""),
        "created_at": _iso(order.get("created_at")),
        "status": order.get("status", "PENDING"),
        "status_label": order.get("status_label", "Pending"),
        "payment_status": order.get("payment_status", "PENDING"),
        "payment_label": order.get("payment_label", "Payment pending"),
        "currency": order.get("currency", "INR"),
        "items": items,
        "item_count": item_count,
        "subtotal": int(order.get("subtotal") or 0),
        "discount": int(order.get("discount") or 0),
        "delivery_fee": int(order.get("delivery_fee") or 0),
        "total": int(order.get("total") or 0),
        "shipping_address": order.get("shipping_address"),
    }