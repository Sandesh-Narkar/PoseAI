"""
PoseAI Nutrition Engine — Multi-Image Product Scanning Session Store
====================================================================
Lightweight in-memory store for multi-image product scanning sessions.

A session allows the user to upload:
  Image 1 — Front of package   (brand/product identification)
  Image 2 — Barcode             (exact product match)
  Image 3 — Nutrition label     (OCR macro extraction)

The session aggregates results from all uploaded images and produces
one final, highest-confidence combined result.

Sessions expire after SESSION_TTL_MINUTES (default 15).
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np

logger = logging.getLogger("poseai.nutrition.session_store")

SESSION_TTL_MINUTES = 15

_store: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(session: dict[str, Any]) -> bool:
    created = session.get("created_at")
    if not isinstance(created, datetime):
        return True
    return _now() - created > timedelta(minutes=SESSION_TTL_MINUTES)


def _purge_expired() -> None:
    """Remove expired sessions (called on every access)."""
    expired = [sid for sid, s in _store.items() if _is_expired(s)]
    for sid in expired:
        del _store[sid]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_session(user_id: str) -> str:
    """Create a new scanning session and return its session_id."""
    session_id = str(uuid.uuid4())
    with _lock:
        _purge_expired()
        _store[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": _now(),
            "images": {
                "front":   None,   # np.ndarray | None
                "barcode": None,
                "label":   None,
            },
            "partial_results": {
                "barcode_detected": None,   # raw barcode string
                "product_match": None,      # ProductResult.to_dict() | None
                "label_parsed": None,       # OCR nutrition dict | None
                "front_text": None,         # raw OCR text from front image
            },
            "final_result": None,
        }
    logger.debug("Created session %s for user %s", session_id, user_id)
    return session_id


def get_session(session_id: str, user_id: str) -> Optional[dict[str, Any]]:
    """Retrieve session if it belongs to user_id and is not expired."""
    with _lock:
        _purge_expired()
        s = _store.get(session_id)
        if not s:
            return None
        if s["user_id"] != user_id:
            return None
        return s


def add_image(session_id: str, user_id: str, image_type: str, img: np.ndarray) -> bool:
    """
    Store an image frame in a session.
    image_type must be one of: "front", "barcode", "label"
    Returns True on success.
    """
    if image_type not in ("front", "barcode", "label"):
        return False
    with _lock:
        s = _store.get(session_id)
        if not s or s["user_id"] != user_id or _is_expired(s):
            return False
        s["images"][image_type] = img
        return True


def set_partial_result(session_id: str, user_id: str, key: str, value: Any) -> bool:
    """Update a partial result field in the session."""
    with _lock:
        s = _store.get(session_id)
        if not s or s["user_id"] != user_id or _is_expired(s):
            return False
        if key in s["partial_results"]:
            s["partial_results"][key] = value
            return True
        return False


def set_final_result(session_id: str, user_id: str, result: dict[str, Any]) -> bool:
    """Store the final combined analysis result for a session."""
    with _lock:
        s = _store.get(session_id)
        if not s or s["user_id"] != user_id or _is_expired(s):
            return False
        s["final_result"] = result
        return True


def close_session(session_id: str) -> None:
    """Remove a session from the store."""
    with _lock:
        _store.pop(session_id, None)


def session_summary(session: dict[str, Any]) -> dict[str, Any]:
    """Return a client-safe summary of session state (no numpy arrays)."""
    imgs = session.get("images", {})
    partial = session.get("partial_results", {})
    return {
        "session_id": session["session_id"],
        "images_uploaded": {
            k: (v is not None) for k, v in imgs.items()
        },
        "barcode_detected": partial.get("barcode_detected"),
        "product_match":    partial.get("product_match"),
        "label_parsed":     partial.get("label_parsed"),
        "has_final_result": session.get("final_result") is not None,
        "ready": _session_is_ready(session),
    }


def _session_is_ready(session: dict[str, Any]) -> bool:
    """True if session has enough data to produce a final result."""
    partial = session.get("partial_results", {})
    imgs = session.get("images", {})
    # Ready if: barcode hit OR label parsed OR at least 2 images uploaded
    has_barcode  = bool(partial.get("barcode_detected") or partial.get("product_match"))
    has_label    = bool(partial.get("label_parsed"))
    images_count = sum(1 for v in imgs.values() if v is not None)
    return has_barcode or has_label or images_count >= 1
