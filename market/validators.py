"""Fitness Market — request validation helpers.

All untrusted query/body values are normalized here before they ever reach
the repository. Failures raise the typed MarketError subclasses so routes
stay thin.
"""

from __future__ import annotations

import re
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId as BsonInvalidId

from .errors import InvalidIdError, InvalidQuantityError, ValidationError

# Reject a request wanting more than this much of any single product.
MAX_CART_QUANTITY = 99
# Bounded page size for the listings endpoint (protects totals/skip math).
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
DEFAULT_PAGE = 1
MAX_PAGE = 500
_MAX_SEARCH_LEN = 100

ALLOWED_SORTS = {
    "recommended",
    "price_asc",
    "price_desc",
    "popularity",
    "newest",
    "rating_desc",
    "discount_desc",
}

ALLOWED_GOALS = {
    "build-muscle",
    "lose-weight",
    "strength",
    "recovery",
    "wellness",
}

_WHITESPACE = re.compile(r"\s+")
_INDIAN_PHONE = re.compile(r"^[6-9]\d{9}$")
_INDIAN_PINCODE = re.compile(r"^\d{6}$")


def parse_product_id(value: Any, field: str = "product_id") -> ObjectId:
    """Return a valid ObjectId or raise INVALID_ID."""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and value.strip():
        candidate = value.strip()
        if _is_valid_object_id_hex(candidate):
            try:
                return ObjectId(candidate)
            except BsonInvalidId:  # pragma: no cover - guarded above
                raise InvalidIdError(f"Invalid {field}: bad ObjectId.")
    raise InvalidIdError(f"Invalid {field}: expected a valid 24-character hex ObjectId.")


def _is_valid_object_id_hex(value: str) -> bool:
    if len(value) != 24:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def parse_quantity(value: Any, *, allow_zero: bool = False) -> int:
    """Validate a cart quantity; reject 0/negative/float/bool/non-integer.

    `allow_zero` is reserved for callers that treat POST quantity=0 as an
    explicit remove request (the frontend instead uses DELETE, so it stays
    unused here).
    """
    if isinstance(value, bool):
        raise InvalidQuantityError(
            "Quantity must be a whole number between 1 and {0}.".format(MAX_CART_QUANTITY)
        )
    if isinstance(value, float):
        raise InvalidQuantityError(
            "Quantity must be a whole number; decimals are not allowed."
        )
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        number = int(value.strip())
    else:
        raise InvalidQuantityError(
            "Quantity must be a whole number between 1 and {0}.".format(MAX_CART_QUANTITY)
        )

    lower_bound = 0 if allow_zero else 1
    if number < lower_bound or number > MAX_CART_QUANTITY:
        if number == 0:
            raise InvalidQuantityError(
                "Quantity must be at least 1. Use the remove option to drop an item."
            )
        raise InvalidQuantityError(
            "Quantity must be between {0} and {1}.".format(lower_bound, MAX_CART_QUANTITY)
        )
    return number


def parse_positive_int(value: Any, field: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValidationError(f"'{field}' must be a positive whole number.")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        number = int(value.strip())
    else:
        raise ValidationError(f"'{field}' must be a positive whole number.")
    if number < 1:
        raise ValidationError(f"'{field}' must be at least 1.")
    if maximum is not None and number > maximum:
        raise ValidationError(f"'{field}' must not exceed {maximum}.")
    return number


def parse_price(value: Any, field: str) -> float:
    """Accept non-negative numeric prices (whole rupees or paisa floats)."""
    if isinstance(value, bool):
        raise ValidationError(f"'{field}' must be a non-negative number.")
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str) and value.strip() != "":
        try:
            number = float(value.strip())
        except ValueError:
            raise ValidationError(f"'{field}' must be a non-negative number.")
    else:
        raise ValidationError(f"'{field}' must be a non-negative number.")
    if number < 0:
        raise ValidationError(f"'{field}' must be a non-negative number.")
    return number


def parse_bool_string(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return False


def parse_min_rating(value: Any) -> float:
    """Minimum star rating filter (0.0 – 5.0), e.g. `rating=4.5`."""
    try:
        number = float(value) if not isinstance(value, bool) else float("nan")
    except (TypeError, ValueError):
        raise ValidationError("'rating' must be a number between 0 and 5.")
    if number < 0 or number > 5:
        raise ValidationError("'rating' must be between 0 and 5.")
    return number


def parse_min_discount(value: Any) -> int:
    """Minimum discount percentage filter (0 – 100), e.g. `discount=20`."""
    if isinstance(value, bool):
        raise ValidationError("'discount' must be a whole number between 0 and 100.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError("'discount' must be a whole number between 0 and 100.")
    if number < 0 or number > 100:
        raise ValidationError("'discount' must be between 0 and 100.")
    return number


def parse_search(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    cleaned = _WHITESPACE.sub(" ", value.strip()).strip()
    if not cleaned:
        return None
    if len(cleaned) > _MAX_SEARCH_LEN:
        raise ValidationError(f"Search query must not exceed {_MAX_SEARCH_LEN} characters.")
    return cleaned


def parse_goal(value: Any) -> str | None:
    """Validate the shop-by-goal key (e.g. `goal=recovery`)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    raw = value.strip().lower() if isinstance(value, str) else str(value).lower()
    _aliases = {
        "muscle-gain": "build-muscle",
        "muscle_gain": "build-muscle",
        "general-fitness": "wellness",
        "general_fitness": "wellness",
        "weight-loss": "lose-weight",
    }
    goal = _aliases.get(raw, raw)
    if goal not in ALLOWED_GOALS:
        raise ValidationError(
            "Invalid goal. Allowed: {0}.".format(", ".join(sorted(ALLOWED_GOALS)))
        )
    return goal


def parse_address(body: dict[str, Any]) -> dict[str, str]:
    """Validate a shipping address; returns a cleaned dict of server-safe fields."""
    address = body.get("address")
    if address is None:
        address = body.get("shipping_address")
    if not isinstance(address, dict):
        raise ValidationError("A shipping 'address' object is required.")

    def _clean(val: Any) -> str:
        return _WHITESPACE.sub(" ", str(val or "")).strip()

    cleaned: dict[str, str] = {
        key: _clean(address.get(key))
        for key in ("full_name", "phone", "line1", "line2", "city", "state", "pincode", "email")
    }
    required = ("full_name", "phone", "line1", "city", "state", "pincode")
    missing = [key for key in required if not cleaned[key]]
    if missing:
        raise ValidationError(
            "Shipping address is missing required fields: {0}.".format(", ".join(missing))
        )
    if not _INDIAN_PHONE.match(cleaned["phone"]):
        raise ValidationError("Phone must be a 10-digit Indian mobile number.")
    if not _INDIAN_PINCODE.match(cleaned["pincode"]):
        raise ValidationError("Pincode must be a 6-digit number.")
    if len(cleaned["full_name"]) > 80:
        raise ValidationError("Full name must not exceed 80 characters.")
    for key in ("line1", "line2"):
        if len(cleaned[key]) > 160:
            raise ValidationError(f"Address field '{key}' is too long (max 160 characters).")
    for key in ("city", "state"):
        if len(cleaned[key]) > 80:
            raise ValidationError(f"Address field '{key}' is too long (max 80 characters).")

    result: dict[str, str] = {
        "full_name": cleaned["full_name"],
        "phone": cleaned["phone"],
        "line1": cleaned["line1"],
        "city": cleaned["city"],
        "state": cleaned["state"],
        "pincode": cleaned["pincode"],
    }
    if cleaned["line2"]:
        result["line2"] = cleaned["line2"]
    if cleaned["email"]:
        result["email"] = cleaned["email"]
    return result


def parse_sort(value: Any) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        return "recommended"
    sort_key = value.strip().lower() if isinstance(value, str) else str(value).lower()
    if sort_key not in ALLOWED_SORTS:
        raise ValidationError(
            "Invalid sort. Allowed: {0}.".format(", ".join(sorted(ALLOWED_SORTS)))
        )
    return sort_key


def parse_categories_qs(value: Any) -> list[str]:
    """Accept a comma-separated list of category slugs (`category=protein,creatine`)."""
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, str):
        raw = value
    else:
        raw = str(value)
    slugs = [part.strip() for part in raw.split(",") if part.strip()]
    if len(slugs) > 8:
        raise ValidationError("Too many categories selected; limit is 8.")
    return slugs