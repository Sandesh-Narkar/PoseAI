"""Fitness Market — HTML pages + REST API blueprint.

Auth model mirrors the rest of the app: `session["user_id"]` (hex string)
is the server-side identity. HTML pages redirect to /login when missing;
API endpoints return a market-style 401 envelope.

Routes
------
Pages:   GET /fitness-market               landing homepage
         GET /fitness-market/products      product discovery (filters/sort/search)
         GET /fitness-market/product/<product_id>   product detail
         GET /fitness-market/favorites     saved products
         GET /fitness-market/checkout      checkout (payment clearly pending)
         GET /fitness-market/orders        order history
         GET /fitness-market/order/<order_id>        order detail
         GET /cart                         cart

Catalog: GET  /api/market/home
         GET  /api/market/categories
         GET  /api/market/products    (search/filter/sort/paginate/goal)
         GET  /api/market/products/<product_id>
         GET  /api/market/products/<product_id>/related
         GET  /api/market/brands

Cart:    GET    /api/market/cart
         POST   /api/market/cart               {product_id, quantity}
         PATCH  /api/market/cart/<product_id>  {quantity}
         DELETE /api/market/cart/<product_id>
         POST   /api/market/cart/clear

Favorites:
         GET    /api/market/favorites
         POST   /api/market/favorites/<product_id>
         DELETE /api/market/favorites/<product_id>

Orders:  POST   /api/market/orders         {address:{...}}
         GET    /api/market/orders
         GET    /api/market/orders/<order_id>

All cart money is computed by the service layer on every read — the cart
collection never stores a price.
"""

from __future__ import annotations

import logging
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify, redirect, request, send_from_directory, session
from werkzeug.wrappers import Response as WerkzeugResponse

from config import Config

try:
    from auth import _is_rate_limited as _market_is_rate_limited
except ImportError:  # pragma: no cover - auth always present in this app
    _market_is_rate_limited = None

from .errors import MarketError, RateLimitedError, UnauthenticatedError, ValidationError
from . import service, validators

logger = logging.getLogger("market.routes")

market_bp = Blueprint("market_bp", __name__)

_FRONTEND_HTML_DIR = Path(__file__).resolve().parent.parent / "frontend" / "html"

# Window used by the header cart badge.
CART_BADGE_WINDOW = 90  # seconds
CART_BADGE_QUOTA = 60  # silent-refresh requests per window


# ==============================================================================
# HELPERS
# ==============================================================================

def _service_ready() -> None:
    """Idempotent catalog seed so a fresh DB is instantly browsable."""
    from .seed import backfill_presentational, seed_if_empty

    seed_if_empty()
    backfill_presentational()


def _current_user_id() -> str:
    user_id = session.get("user_id")
    if user_id is None:
        raise UnauthenticatedError("Authentication required to access the Fitness Market.")
    return str(user_id)


def market_login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    """API guard — returns a market-style 401 envelope when not authed."""

    @wraps(view)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        if session.get("user_id") is None:
            return jsonify(
                {"success": False, "error": UnauthenticatedError("Authentication required.").to_payload()}
            ), 401
        return view(*args, **kwargs)

    return _wrapped


def rate_limit_mutations(view: Callable[..., Any]) -> Callable[..., Any]:
    """Apply the app's in-memory sliding-window rate limiter to cart writes."""

    @wraps(view)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        if (
            _market_is_rate_limited is not None
            and getattr(Config, "RATE_LIMIT_ENABLED", False)
            and _market_is_rate_limited("market_mutation", limit=120, window=60)
        ):
            raise RateLimitedError("Too many cart updates. Please slow down and try again.")
        return view(*args, **kwargs)

    return _wrapped


def _page_guard() -> WerkzeugResponse | None:
    if session.get("user_id") is None:
        return redirect("/login")
    return None


def _serve_market_page(filename: str) -> WerkzeugResponse:
    return send_from_directory(_FRONTEND_HTML_DIR, filename)


def _current_fitness_goal() -> str:
    """Read the user's stored fitness goal for recommendations (best effort).

    Returns "" when the profile goal is unset or the read fails — the market
    layer never hard-fails on profile data it does not own.
    """
    try:
        from bson import ObjectId

        from database.mongo import get_db

        user_id = session.get("user_id")
        if not user_id:
            return ""
        users = get_db()["users"]
        doc = None
        try:
            doc = users.find_one({"_id": ObjectId(str(user_id))})
        except Exception:  # noqa: BLE001 - try the string fallback
            doc = users.find_one({"_id": user_id}) if doc is None else doc
        if doc is None:
            doc = users.find_one({"username": str(user_id)})
        if not doc:
            return ""
        goal = doc.get("fitness_goal")
        return str(goal).strip() if goal else ""
    except Exception:  # noqa: BLE001 - recommendations degrade silently
        return ""


@market_bp.errorhandler(MarketError)
def _handle_market_error(error: MarketError) -> tuple[Any, int]:
    logger.info("Market error %s: %s", error.code, error.message)
    payload = {"success": False, "error": error.to_payload()}
    if error.code == "INSUFFICIENT_STOCK":
        payload["error"]["available_quantity"] = error.available_quantity
    return jsonify(payload), error.status_code


def _parse_browse_params(args: Any) -> dict[str, Any]:
    """Validate all listing query params up-front; raise VALIDATION_ERROR."""
    query_params: dict[str, Any] = {
        "limit": validators.DEFAULT_PAGE_SIZE,
        "page": validators.DEFAULT_PAGE,
    }
    if args.get("page") not in (None, ""):
        query_params["page"] = validators.parse_positive_int(args.get("page"), "page")
    if args.get("limit") not in (None, ""):
        query_params["limit"] = validators.parse_positive_int(args.get("limit"), "limit")
    if args.get("search") not in (None, ""):
        query_params["search"] = validators.parse_search(args.get("search"))
    raw_cats = []
    for key in ("categories", "category"):
        vals = args.getlist(key) if hasattr(args, "getlist") else [args.get(key)]
        for v in vals:
            if v not in (None, ""):
                raw_cats.extend([c.strip() for c in str(v).split(",") if c.strip()])
    if raw_cats:
        seen = set()
        deduped = []
        for c in raw_cats:
            if c.lower() not in seen:
                seen.add(c.lower())
                deduped.append(c)
        query_params["categories"] = deduped
        if len(deduped) == 1:
            query_params["category"] = deduped[0]
    if args.get("brands") not in (None, ""):
        query_params["brands"] = [b.strip() for b in args.get("brands").split(",") if b.strip()]
    if args.get("brand") not in (None, ""):
        brand_value = str(args.get("brand"))
        seen = set(query_params.get("brands") or [])
        if brand_value not in seen:
            query_params.setdefault("brands", []).append(brand_value)
    if args.get("in_stock") not in (None, ""):
        query_params["in_stock"] = validators.parse_bool_string(args.get("in_stock"))
    if args.get("deals") not in (None, ""):
        query_params["is_deal"] = validators.parse_bool_string(args.get("deals"))
    if args.get("min_price") not in (None, ""):
        query_params["min_price"] = validators.parse_price(args.get("min_price"), "min_price")
    if args.get("max_price") not in (None, ""):
        query_params["max_price"] = validators.parse_price(args.get("max_price"), "max_price")
    if args.get("rating") not in (None, ""):
        query_params["rating"] = validators.parse_min_rating(args.get("rating"))
    if args.get("discount") not in (None, ""):
        query_params["discount"] = validators.parse_min_discount(args.get("discount"))
    if args.get("goal") not in (None, ""):
        query_params["goal"] = validators.parse_goal(args.get("goal"))
    query_params["sort"] = validators.parse_sort(args.get("sort"))
    return query_params


def _wrapped_positive_int(value: Any, field: str, default: int | None = None) -> int:
    try:
        return validators.parse_positive_int(value, field)
    except ValueError:
        if default is not None:
            return default
        raise


def _get_json_body() -> dict[str, Any]:
    body = request.get_json(silent=True)
    if body is None or not isinstance(body, dict):
        raise ValidationError("Request body must be a JSON object.")
    return body


def _require_quantity(body: dict[str, Any]) -> int:
    if "quantity" not in body:
        raise ValidationError("Field 'quantity' is required.")
    return validators.parse_quantity(body.get("quantity"))


def _require_product_id(body: dict[str, Any]) -> str:
    if not body.get("product_id"):
        raise ValidationError("Field 'product_id' is required.")
    return str(body.get("product_id"))


# ==============================================================================
# ROUTES — HTML PAGES
# ==============================================================================

@market_bp.route("/fitness-market", methods=["GET"])
def market_page():
    guard = _page_guard()
    if guard is not None:
        return guard
    return _serve_market_page("fitness_market.html")


@market_bp.route("/fitness-market/products", methods=["GET"])
def products_page():
    guard = _page_guard()
    if guard is not None:
        return guard
    return _serve_market_page("products.html")


@market_bp.route("/fitness-market/favorites", methods=["GET"])
def favorites_page():
    guard = _page_guard()
    if guard is not None:
        return guard
    return _serve_market_page("favorites.html")


@market_bp.route("/fitness-market/checkout", methods=["GET"])
def checkout_page():
    guard = _page_guard()
    if guard is not None:
        return guard
    return _serve_market_page("checkout.html")


@market_bp.route("/fitness-market/orders", methods=["GET"])
def orders_page():
    guard = _page_guard()
    if guard is not None:
        return guard
    return _serve_market_page("orders.html")


@market_bp.route("/fitness-market/order/<order_id>", methods=["GET"])
def order_detail_page(order_id: str):
    guard = _page_guard()
    if guard is not None:
        return guard
    return _serve_market_page("orders.html")


@market_bp.route("/fitness-market/product", methods=["GET"])
@market_bp.route("/market/product", methods=["GET"])
@market_bp.route("/fitness-market/product/<product_id>", methods=["GET"])
@market_bp.route("/market/product/<product_id>", methods=["GET"])
def product_detail_page(product_id: str = ""):
    guard = _page_guard()
    if guard is not None:
        return guard
    return _serve_market_page("product_detail.html")


@market_bp.route("/market", methods=["GET"])
def market_alias():
    return redirect("/fitness-market")


@market_bp.route("/market/products", methods=["GET"])
def market_products_alias():
    return redirect("/fitness-market/products")


@market_bp.route("/cart", methods=["GET"])
def cart_page():
    guard = _page_guard()
    if guard is not None:
        return guard
    return _serve_market_page("cart.html")


# ==============================================================================
# ROUTES — CATALOG API
# ==============================================================================

@market_bp.route("/api/market/home", methods=["GET"])
@market_login_required
def api_home():
    try:
        _service_ready()
        user_id = _current_user_id()
        fitness_goal = _current_fitness_goal()
        home_result = service.home(user_id, fitness_goal)
        nested = home_result.get("home", {})
        return jsonify({"success": True, "home": nested, **nested})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] home failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/categories", methods=["GET"])
@market_login_required
def api_categories():
    try:
        _service_ready()
        return jsonify({"success": True, "categories": service.categories()})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] categories failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/brands", methods=["GET"])
@market_login_required
def api_brands():
    try:
        return jsonify({"success": True, "brands": service.brands()})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] brands failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/products", methods=["GET"])
@market_login_required
def api_list_products():
    try:
        _service_ready()
        user_id = _current_user_id()
        params = _parse_browse_params(request.args)
        result = service.browse(params, favorite_ids=service.favorite_ids(user_id))
        return jsonify({"success": True, **result})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] products listing failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/search", methods=["GET"])
@market_login_required
def api_search_products():
    try:
        _service_ready()
        user_id = _current_user_id()
        params = _parse_browse_params(request.args)
        query = request.args.get("q") or request.args.get("query") or request.args.get("search") or ""
        if query:
            params["search"] = validators.parse_search(query)
        result = service.browse(params, favorite_ids=service.favorite_ids(user_id))
        return jsonify({"success": True, **result})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] products search failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/products/<product_id>", methods=["GET"])
@market_login_required
def api_product_detail(product_id: str):
    try:
        validators.parse_product_id(product_id)
        user_id = _current_user_id()
        dto = service.product_detail(product_id, favorite_ids=service.favorite_ids(user_id))
        try:
            service.record_recently_viewed(user_id, product_id)
        except Exception:
            pass
        return jsonify({"success": True, "product": dto})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] product detail failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/products/<product_id>/related", methods=["GET"])
@market_login_required
def api_related_products(product_id: str):
    try:
        oid = validators.parse_product_id(product_id)
        user_id = _current_user_id()
        dto = service.product_detail(oid, favorite_ids=service.favorite_ids(user_id))
        related = service.related_products(oid, dto["category"], favorite_ids=service.favorite_ids(user_id))
        return jsonify({"success": True, "products": related})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] related products failed")
        raise MarketError(str(error))


# ==============================================================================
# ROUTES — CART API
# ==============================================================================

@market_bp.route("/api/market/cart", methods=["GET"])
@market_login_required
def api_get_cart():
    try:
        user_id = _current_user_id()
        cart = service.cart_payload(user_id)
        return jsonify({"success": True, "cart": cart, "data": cart})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] cart read failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/cart", methods=["POST"])
@market_login_required
@rate_limit_mutations
def api_add_to_cart():
    try:
        user_id = _current_user_id()
        body = _get_json_body()
        product_id = _require_product_id(body)
        quantity = _require_quantity(body)
        cart = service.add_to_cart(user_id, product_id, quantity)
        return jsonify({"success": True, "message": "Added to cart.", "cart": cart}), 201
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] cart add failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/cart/clear", methods=["POST"])
@market_login_required
@rate_limit_mutations
def api_clear_cart():
    try:
        user_id = _current_user_id()
        cart = service.clear(user_id)
        return jsonify({"success": True, "message": "Cart cleared.", "cart": cart})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] cart clear failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/cart/<product_id>", methods=["PATCH"])
@market_login_required
@rate_limit_mutations
def api_update_quantity(product_id: str):
    try:
        user_id = _current_user_id()
        validators.parse_product_id(product_id)
        body = _get_json_body()
        quantity = _require_quantity(body)
        cart = service.update_quantity(user_id, product_id, quantity)
        return jsonify({"success": True, "message": "Cart updated.", "cart": cart})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] cart update failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/cart/<product_id>", methods=["DELETE"])
@market_login_required
@rate_limit_mutations
def api_remove_item(product_id: str):
    try:
        user_id = _current_user_id()
        validators.parse_product_id(product_id)
        cart = service.remove_item(user_id, product_id)
        return jsonify({"success": True, "message": "Removed from cart.", "cart": cart})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] cart remove failed")
        raise MarketError(str(error))


# ==============================================================================
# ROUTES — CART BADGE (lightweight, small page-load refresh)
# ==============================================================================

@market_bp.route("/api/market/cart-count", methods=["GET"])
@market_login_required
def api_cart_count():
    try:
        if (
            _market_is_rate_limited is not None
            and getattr(Config, "RATE_LIMIT_ENABLED", False)
            and _market_is_rate_limited("market_cart_count", limit=CART_BADGE_QUOTA, window=CART_BADGE_WINDOW)
        ):
            return jsonify({"success": True, "item_count": 0})
        user_id = _current_user_id()
        return jsonify({"success": True, "item_count": service.cart_count(user_id)})
    except UnauthenticatedError as error:
        return jsonify({"success": False, "error": error.to_payload()}), 401
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] cart count failed")
        return jsonify({"success": True, "item_count": 0})


# ==============================================================================
# ROUTES — FAVORITES
# ==============================================================================

@market_bp.route("/api/market/favorites", methods=["GET"])
@market_login_required
def api_favorites():
    try:
        user_id = _current_user_id()
        result = service.favorites(user_id)
        return jsonify({"success": True, **result})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] favorites read failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/favorites/<product_id>", methods=["POST"])
@market_login_required
@rate_limit_mutations
def api_add_favorite(product_id: str):
    try:
        user_id = _current_user_id()
        validators.parse_product_id(product_id)
        result = service.add_favorite(user_id, product_id)
        return jsonify({"success": True, "message": "Added to favorites.", **result}), 201
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] favorites add failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/favorites/<product_id>", methods=["DELETE"])
@market_login_required
@rate_limit_mutations
def api_remove_favorite(product_id: str):
    try:
        user_id = _current_user_id()
        validators.parse_product_id(product_id)
        result = service.remove_favorite(user_id, product_id)
        return jsonify({"success": True, "message": "Removed from favorites.", **result})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] favorites remove failed")
        raise MarketError(str(error))


# Wishlist aliases matching spec requirement 14
@market_bp.route("/api/market/wishlist", methods=["GET"])
@market_login_required
def api_get_wishlist():
    return api_favorites()


@market_bp.route("/api/market/wishlist", methods=["POST"])
@market_bp.route("/api/market/wishlist/<product_id>", methods=["POST"])
@market_login_required
@rate_limit_mutations
def api_post_wishlist(product_id: str | None = None):
    if not product_id:
        body = request.get_json(silent=True) or {}
        product_id = body.get("product_id")
    if not product_id:
        raise ValidationError("Field 'product_id' is required.")
    return api_add_favorite(str(product_id))


@market_bp.route("/api/market/wishlist/<product_id>", methods=["DELETE"])
@market_login_required
@rate_limit_mutations
def api_delete_wishlist(product_id: str):
    return api_remove_favorite(product_id)


# ==============================================================================
# ROUTES — ORDERS
# ==============================================================================

@market_bp.route("/api/market/orders", methods=["POST"])
@market_login_required
@rate_limit_mutations
def api_create_order():
    try:
        user_id = _current_user_id()
        body = _get_json_body()
        address = validators.parse_address(body)
        order = service.create_order(user_id, address)
        return jsonify({"success": True, "message": "Order placed.", "order": order, "data": order}), 201
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] order create failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/orders", methods=["GET"])
@market_login_required
def api_list_orders():
    try:
        user_id = _current_user_id()
        result = service.orders(user_id)
        return jsonify({"success": True, **result})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] orders listing failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/orders/<order_id>", methods=["GET"])
@market_login_required
def api_order_detail(order_id: str):
    try:
        validators.parse_product_id(order_id, field="order_id")
        user_id = _current_user_id()
        order = service.order_detail(user_id, order_id)
        return jsonify({"success": True, "order": order})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] order detail failed")
        raise MarketError(str(error))


# ==============================================================================
# ROUTES — RECENTLY VIEWED
# ==============================================================================

@market_bp.route("/api/market/recently-viewed", methods=["GET"])
@market_login_required
def api_get_recently_viewed():
    try:
        user_id = _current_user_id()
        limit = request.args.get("limit", 8)
        try:
            limit = int(limit)
        except Exception:
            limit = 8
        fav_ids = service.favorite_ids(user_id)
        result = service.recently_viewed(user_id, limit=limit, favorite_ids=fav_ids)
        return jsonify({"success": True, **result})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] recently viewed get failed")
        raise MarketError(str(error))


@market_bp.route("/api/market/recently-viewed", methods=["POST"])
@market_login_required
def api_post_recently_viewed():
    try:
        user_id = _current_user_id()
        body = _get_json_body()
        pid = body.get("product_id")
        if not pid:
            raise ValidationError("Field 'product_id' is required.")
        service.record_recently_viewed(user_id, pid)
        return jsonify({"success": True, "message": "Product recorded in recently viewed."})
    except MarketError as error:
        raise error
    except Exception as error:  # noqa: BLE001
        logger.exception("[MARKET] recently viewed post failed")
        raise MarketError(str(error))
