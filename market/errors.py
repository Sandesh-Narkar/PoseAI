"""Fitness Market — typed domain errors.

Every market API failure surfaces as a structured error envelope:

    {"success": false, "error": {"code", "message", ...}}

Status-code mapping for the market contract:
    UNAUTHENTICATED         -> 401
    FORBIDDEN               -> 403
    INVALID_ID              -> 400
    VALIDATION_ERROR        -> 400
    INVALID_QUANTITY        -> 422
    PRODUCT_NOT_FOUND       -> 404
    PRODUCT_INACTIVE        -> 409
    OUT_OF_STOCK            -> 409
    INSUFFICIENT_STOCK      -> 409 (+ available_quantity)
    RATE_LIMITED            -> 429
    SERVER_ERROR            -> 500
"""

from __future__ import annotations

from typing import Any


class MarketError(Exception):
    """Base class for all market domain errors."""

    status_code: int = 500
    code: str = "SERVER_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def to_payload(self) -> dict[str, Any]:
        """Build the `error` object of the wire envelope."""
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        for key, value in self.details.items():
            payload.setdefault(key, value)
        return payload


class UnauthenticatedError(MarketError):
    status_code = 401
    code = "UNAUTHENTICATED"


class ForbiddenError(MarketError):
    status_code = 403
    code = "FORBIDDEN"


class InvalidIdError(MarketError):
    status_code = 400
    code = "INVALID_ID"


class ValidationError(MarketError):
    status_code = 400
    code = "VALIDATION_ERROR"


class InvalidQuantityError(MarketError):
    status_code = 422
    code = "INVALID_QUANTITY"


class ProductNotFoundError(MarketError):
    status_code = 404
    code = "PRODUCT_NOT_FOUND"


class OrderNotFoundError(MarketError):
    status_code = 404
    code = "ORDER_NOT_FOUND"


class ProductInactiveError(MarketError):
    status_code = 409
    code = "PRODUCT_INACTIVE"


class OutOfStockError(MarketError):
    status_code = 409
    code = "OUT_OF_STOCK"


class InsufficientStockError(MarketError):
    status_code = 409
    code = "INSUFFICIENT_STOCK"

    def __init__(self, message: str, available_quantity: int) -> None:
        super().__init__(message, details={"available_quantity": available_quantity})
        self.available_quantity = available_quantity


class RateLimitedError(MarketError):
    status_code = 429
    code = "RATE_LIMITED"