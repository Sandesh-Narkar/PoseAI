"""PoseAI Fitness Market package.

Implements the commerce feature isolated from the workout/game engines:

    market.routes      Flask blueprint (HTML pages + /api/market/* REST)
    market.service     business logic / server-authoritative cart math
    market.repository  Mongo access (products/categories/carts)
    market.schemas     response DTOs, owned by this package
    market.validators  request validation + typed errors
    market.seed        idempotent catalog seeder (python -m market.seed)

Prime directive: market data (products/categories/carts) is a separate
source of truth from workout analytics and game data. Nothing in this
package reads or mutates workout/game/user collections.
"""

from __future__ import annotations

from .routes import market_bp

__all__ = ["market_bp"]