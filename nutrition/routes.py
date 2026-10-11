"""
PoseAI Nutrition Intelligence System — REST API Blueprint
=========================================================
Endpoints for food scanning, confirmation, daily summaries,
macro breakdown, meal timeline management, and activity recommendations.

All routes are strictly scoped to the authenticated user (session["user_id"]).
"""

from __future__ import annotations

import logging
from datetime import date
from functools import wraps
from typing import Any, Callable

from flask import Blueprint, jsonify, request, session

from nutrition.food_db import (
    FOOD_DATABASE,
    get_food_by_id,
    scale_nutrition,
    search_foods,
)
from nutrition.repository import (
    delete_custom_food,
    delete_scan,
    get_daily_nutrition,
    get_nutrition_history,
    get_scan_by_id,
    get_scans_by_date,
    list_custom_foods,
    recalculate_daily_nutrition,
    save_custom_food,
    save_scan,
    update_scan,
)
from nutrition.service import (
    calculate_user_targets,
    generate_daily_insight,
    get_today_nutrition_dashboard,
    suggest_exercise_for_recent_food,
)
from nutrition.vision import (
    analyze_food_image,
    decode_base64_frame,
    validate_and_decode_image,
)
from nutrition.product_lookup import get_product_lookup_service
from nutrition.validator import validate_nutrition, sanitize_nutrition
from nutrition import session_store as _sess
from database.workouts import get_workouts_collection

logger = logging.getLogger("poseai.nutrition.routes")

nutrition_bp = Blueprint("nutrition", __name__, url_prefix="/api/nutrition")


def login_required(f: Callable) -> Callable:
    """Ensure endpoint is accessed only by authenticated session."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({
                "success": False,
                "error": "Authentication required. Please log in.",
            }), 401
        return f(*args, **kwargs)
    return decorated_function


# ── SCAN & ANALYSIS ───────────────────────────────────────────────────

@nutrition_bp.route("/gemini-status", methods=["GET"])
@login_required
def gemini_status() -> Any:
    """Return status of Gemini 2.5 Flash Vision AI engine."""
    from nutrition.gemini_vision import is_gemini_available, DEFAULT_GEMINI_MODEL
    return jsonify({
        "success": True,
        "data": {
            "available": is_gemini_available(),
            "model": DEFAULT_GEMINI_MODEL,
            "engine": "Google GenAI 2.5 Flash",
        },
    }), 200


@nutrition_bp.route("/scan", methods=["POST"])
@nutrition_bp.route("/recognize", methods=["POST"])
@login_required
def scan_food() -> Any:
    """
    Analyze food image from either a multipart file upload or base64 frame.
    Returns estimated detection, nutrition breakdown, confidence, and quality.
    """
    img_np = None
    user_hint = None
    meal_type = "lunch"

    # Check multipart file upload first
    if "file" in request.files:
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "No file selected."}), 400
        raw_bytes = file.read()
        user_hint = request.form.get("hint")
        meal_type = request.form.get("meal_type", "lunch")
        img_np, err = validate_and_decode_image(raw_bytes)
        if err:
            return jsonify({"success": False, "error": err}), 400

    # Else check JSON base64 payload
    elif request.is_json:
        data = request.get_json() or {}
        image_data = data.get("image")
        user_hint = data.get("hint")
        meal_type = data.get("meal_type", "lunch")
        if not image_data:
            return jsonify({"success": False, "error": "No image data provided."}), 400
        img_np, err = decode_base64_frame(image_data)
        if err:
            return jsonify({"success": False, "error": err}), 400
    else:
        return jsonify({"success": False, "error": "Unsupported request format. Use multipart/form-data or JSON."}), 400

    if img_np is None:
        return jsonify({"success": False, "error": "Could not process image."}), 400

    # Run vision analysis
    try:
        analysis_result = analyze_food_image(img_np, user_hint=user_hint, default_meal_type=meal_type)
        resp = {
            "success": True,
            "data": analysis_result,
        }
        for k in ("status", "food", "recognition", "portion", "nutrition", "nutrition_source", "requires_confirmation", "candidates", "debug"):
            if k in analysis_result:
                resp[k] = analysis_result[k]
        return jsonify(resp), 200
    except Exception as e:
        logger.exception("Food vision analysis encountered an error: %s", e)
        return jsonify({
            "success": False,
            "error": "We couldn't analyze this image. Please try again or enter food manually.",
        }), 500


# ── LOG & CONFIRMATION ────────────────────────────────────────────────

@nutrition_bp.route("/confirm", methods=["POST"])
@login_required
def confirm_food_log() -> Any:
    """
    Save confirmed food scan to the user's daily nutrition log.
    Automatically re-aggregates today's totals.
    """
    user_id = str(session["user_id"])
    payload = request.get_json(silent=True) or {}

    canonical_id = payload.get("canonical_id")
    food_name = payload.get("food_name")

    # If user confirmed an uncertain candidate without providing manual nutrition:
    if (not payload.get("detected_foods") or not payload.get("nutrition")) and (canonical_id or food_name):
        from nutrition.food_db import resolve_canonical_food, get_food_by_id
        matched = get_food_by_id(canonical_id) if canonical_id else None
        if not matched and food_name:
            matched = resolve_canonical_food(food_name)
        if matched:
            nut = dict(matched.get("nutrition", {}))
            p_desc = matched.get("serving_description", f"1 {matched.get('serving_unit', 'serving')}")
            payload["detected_foods"] = [{
                "id": matched.get("canonical_id", canonical_id or "custom"),
                "name": matched.get("name", food_name),
                "quantity": p_desc,
                "serving_qty": 1.0,
                "serving_unit": matched.get("serving_unit", "serving"),
                "estimated_weight_g": matched.get("serving_size_g"),
                "confidence": payload.get("confidence", 1.0),
            }]
            payload["nutrition"] = nut
            payload["source"] = "food_database"

    if not payload.get("detected_foods") and not payload.get("nutrition"):
        return jsonify({"success": False, "error": "Incomplete nutrition record."}), 400

    meal_type = (payload.get("meal_type") or "lunch").lower()
    if meal_type not in {"breakfast", "lunch", "snack", "dinner"}:
        meal_type = "lunch"

    scan_data = {
        "date": payload.get("date") or date.today().isoformat(),
        "meal_type": meal_type,
        "image_reference": payload.get("image_reference", ""),
        "detected_foods": payload.get("detected_foods", []),
        "nutrition": payload.get("nutrition", {}),
        "food_quality": payload.get("food_quality", {}),
        "source": payload.get("source", "image_ai"),
        "confidence": payload.get("confidence", 0.95),
        "notes": payload.get("notes", ""),
    }

    try:
        scan_id = save_scan(user_id, scan_data)
        return jsonify({
            "success": True,
            "message": "Food successfully logged to today's nutrition.",
            "scan_id": scan_id,
        }), 201
    except Exception as e:
        logger.exception("Failed to save nutrition scan: %s", e)
        return jsonify({"success": False, "error": "Could not save food log."}), 500

# ── READ TODAY / DASHBOARD ───────────────────────────────────────────

@nutrition_bp.route("/today", methods=["GET"])
@login_required
def get_today_summary() -> Any:
    """Retrieve full dashboard payload for today."""
    user_id = str(session["user_id"])
    try:
        payload = get_today_nutrition_dashboard(user_id)
        return jsonify({"success": True, "data": payload}), 200
    except Exception as e:
        logger.exception("Failed to retrieve today's nutrition: %s", e)
        return jsonify({"success": False, "error": "Nutrition data couldn't be loaded."}), 500


@nutrition_bp.route("/day/<date_str>", methods=["GET"])
@login_required
def get_day_summary(date_str: str) -> Any:
    """Retrieve nutrition record for a specific date."""
    user_id = str(session["user_id"])
    try:
        daily = get_daily_nutrition(user_id, date_str)
        scans = get_scans_by_date(user_id, date_str)
        return jsonify({
            "success": True,
            "data": {
                "date": date_str,
                "daily": daily,
                "scans": scans,
            },
        }), 200
    except Exception as e:
        logger.exception("Failed to fetch day nutrition for %s: %s", date_str, e)
        return jsonify({"success": False, "error": "Could not retrieve date record."}), 500


# ── EDIT / DELETE SCANS ───────────────────────────────────────────────

@nutrition_bp.route("/scan/<scan_id>", methods=["PUT"])
@login_required
def edit_scan(scan_id: str) -> Any:
    """Edit portion, meal type, or nutrition of a previously logged scan."""
    user_id = str(session["user_id"])
    payload = request.get_json(silent=True) or {}

    existing = get_scan_by_id(user_id, scan_id)
    if not existing:
        return jsonify({"success": False, "error": "Scan record not found."}), 404

    updates: dict[str, Any] = {}
    if "meal_type" in payload:
        updates["meal_type"] = str(payload["meal_type"]).lower()
    if "nutrition" in payload:
        updates["nutrition"] = payload["nutrition"]
    if "detected_foods" in payload:
        updates["detected_foods"] = payload["detected_foods"]
    if "source" in payload:
        updates["source"] = payload["source"]
    else:
        updates["source"] = "user_corrected"

    updated = update_scan(user_id, scan_id, updates)
    if updated:
        return jsonify({"success": True, "message": "Food log updated."}), 200
    return jsonify({"success": False, "error": "Could not update record."}), 500


@nutrition_bp.route("/scan/<scan_id>", methods=["DELETE"])
@login_required
def remove_scan(scan_id: str) -> Any:
    """Delete a scan from today's timeline and recompute daily totals."""
    user_id = str(session["user_id"])
    deleted = delete_scan(user_id, scan_id)
    if deleted:
        return jsonify({"success": True, "message": "Food record removed."}), 200
    return jsonify({"success": False, "error": "Scan not found or could not be removed."}), 404


# ── INSIGHTS, TARGETS, & TRENDS ───────────────────────────────────────

@nutrition_bp.route("/insights", methods=["GET"])
@login_required
def get_insights() -> Any:
    """Dynamic AI daily insights combining food intake and workout data."""
    user_id = str(session["user_id"])
    today_str = date.today().isoformat()
    daily = get_daily_nutrition(user_id, today_str)
    targets = calculate_user_targets(user_id)

    workout_coll = get_workouts_collection()
    workouts = list(workout_coll.find({"user_id": user_id, "date": today_str}))

    insight = generate_daily_insight(
        daily.get("totals", {}),
        targets,
        daily.get("activity", {}),
        workouts,
    )
    return jsonify({"success": True, "data": insight}), 200


@nutrition_bp.route("/targets", methods=["GET"])
@login_required
def get_targets() -> Any:
    """Profile-based personalized targets."""
    user_id = str(session["user_id"])
    targets = calculate_user_targets(user_id)
    return jsonify({"success": True, "data": targets}), 200


@nutrition_bp.route("/trends", methods=["GET"])
@nutrition_bp.route("/history", methods=["GET"])
@login_required
def get_trends() -> Any:
    """Retrieve historical trends for 7, 30, or 90 days."""
    user_id = str(session["user_id"])
    days_arg = request.args.get("days", "7")
    try:
        days = int(days_arg)
        if days not in {7, 30, 90}:
            days = 7
    except ValueError:
        days = 7

    history = get_nutrition_history(user_id, days=days)

    # Compute summary aggregates
    logged_days = [h for h in history if h.get("totals", {}).get("calories_kcal", 0) > 0]
    avg_cal = (
        int(round(sum(h["totals"]["calories_kcal"] for h in logged_days) / len(logged_days)))
        if logged_days else 0
    )
    avg_prot = (
        round(sum(h["totals"]["protein_g"] for h in logged_days) / len(logged_days), 1)
        if logged_days else 0.0
    )
    total_workout_kcal = sum(h.get("activity", {}).get("estimated_workout_kcal", 0) for h in history)

    return jsonify({
        "success": True,
        "data": {
            "days": days,
            "history": history,
            "weekly_avg_calories": avg_cal,
            "weekly_avg_protein": avg_prot,
            "total_workout_kcal": total_workout_kcal,
            "logging_consistency_days": len(logged_days),
        },
    }), 200


@nutrition_bp.route("/search", methods=["GET"])
@login_required
def search_catalog() -> Any:
    """Search food database for manual selection or candidate resolution."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"success": True, "data": FOOD_DATABASE[:15], "foods": FOOD_DATABASE[:15]}), 200
    by_id = get_food_by_id(query)
    if by_id:
        return jsonify({"success": True, "data": [by_id], "foods": [by_id]}), 200
    items = search_foods(query, limit=15)
    return jsonify({"success": True, "data": items, "foods": items}), 200


# ── MULTI-IMAGE PRODUCT SESSION ───────────────────────────────────────

@nutrition_bp.route("/product-session", methods=["POST"])
@login_required
def product_session() -> Any:
    """
    Create or update a multi-image product scanning session.

    Body (JSON or multipart):
      session_id   : optional — omit to create a new session
      image_type   : "front" | "barcode" | "label"
      image        : base64 data URI  OR  multipart file field "file"

    Returns:
      { session_id, summary: {images_uploaded, barcode_detected, product_match, ready} }
    """
    user_id = str(session["user_id"])

    # Decode image
    img_np = None
    image_type = "front"

    if "file" in request.files:
        file = request.files["file"]
        image_type = request.form.get("image_type", "front")
        session_id = request.form.get("session_id") or ""
        raw_bytes = file.read()
        img_np, err = validate_and_decode_image(raw_bytes)
        if err:
            return jsonify({"success": False, "error": err}), 400
    elif request.is_json:
        data = request.get_json() or {}
        image_type = data.get("image_type", "front")
        session_id = data.get("session_id") or ""
        image_data = data.get("image")
        if not image_data:
            return jsonify({"success": False, "error": "No image data provided."}), 400
        img_np, err = decode_base64_frame(image_data)
        if err:
            return jsonify({"success": False, "error": err}), 400
    else:
        return jsonify({"success": False, "error": "Unsupported request format."}), 400

    if img_np is None:
        return jsonify({"success": False, "error": "Could not decode image."}), 400

    # Create or fetch session
    if not session_id:
        session_id = _sess.create_session(user_id)
    else:
        sess = _sess.get_session(session_id, user_id)
        if not sess:
            session_id = _sess.create_session(user_id)

    # Store the image
    _sess.add_image(session_id, user_id, image_type, img_np)

    # Run partial analysis for this image type
    partial_update: dict[str, Any] = {}
    try:
        if image_type == "barcode":
            from nutrition.barcode import detect_barcode_in_image, lookup_barcode
            bc, _fmt = detect_barcode_in_image(img_np)
            if bc:
                _sess.set_partial_result(session_id, user_id, "barcode_detected", bc)
                match = lookup_barcode(bc)
                if match and match.get("product"):
                    _sess.set_partial_result(session_id, user_id, "product_match", match["product"])
                    partial_update["barcode"] = bc
                    partial_update["product"] = {
                        "brand": match["product"].get("brand"),
                        "product_name": match["product"].get("product_name"),
                        "confidence": match.get("confidence", 0.98),
                    }

        elif image_type == "label":
            from nutrition.ocr_engine import extract_text_from_image, parse_nutrition_facts_text
            text = extract_text_from_image(img_np)
            label = parse_nutrition_facts_text(text)
            if label:
                _sess.set_partial_result(session_id, user_id, "label_parsed",
                                        label["nutrition_per_serving"])
                partial_update["label"] = label["nutrition_per_serving"]

        elif image_type == "front":
            from nutrition.ocr_engine import extract_text_from_image
            text = extract_text_from_image(img_np)
            _sess.set_partial_result(session_id, user_id, "front_text", text)
            # Try product name search from front text
            if text and len(text) > 5:
                svc = get_product_lookup_service()
                candidates = svc.lookup_by_text(text)
                if candidates:
                    top = candidates[0]
                    partial_update["product_candidates"] = [
                        {"brand": c.brand, "product_name": c.product_name, "id": c.id}
                        for c in candidates[:3]
                    ]

    except Exception as exc:
        logger.warning("Partial session analysis error: %s", exc)

    sess = _sess.get_session(session_id, user_id)
    summary = _sess.session_summary(sess) if sess else {}
    summary.update(partial_update)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "summary": summary,
    }), 200


@nutrition_bp.route("/confirm-session", methods=["POST"])
@login_required
def confirm_session() -> Any:
    """
    Finalize a product scanning session.
    Runs NutritionValidator, saves to MongoDB.

    Body: { session_id, meal_type, corrections: {...optional overrides} }
    """
    user_id = str(session["user_id"])
    payload = request.get_json(silent=True) or {}

    session_id = payload.get("session_id", "")
    if not session_id:
        return jsonify({"success": False, "error": "session_id required."}), 400

    sess = _sess.get_session(session_id, user_id)
    if not sess:
        return jsonify({"success": False, "error": "Session not found or expired."}), 404

    meal_type = (payload.get("meal_type") or "lunch").lower()
    if meal_type not in {"breakfast", "lunch", "snack", "dinner"}:
        meal_type = "lunch"

    # Build result from session partial results
    partial = sess["partial_results"]
    product_match  = partial.get("product_match")
    label_parsed   = partial.get("label_parsed")

    nutrition: dict[str, Any] = {}
    detected_foods: list[dict[str, Any]] = []
    source_type    = "unknown"
    accuracy_level = "unknown"
    confidence     = 0.30
    verified       = False
    food_quality   = {"classification": "unknown", "processing_level": "unknown", "reasons": []}

    # Priority: barcode product > label OCR > unknown
    if product_match:
        nut = product_match.get("nutrition_per_serving", {})
        nutrition = dict(nut)
        detected_foods = [{
            "id": product_match.get("id", "product"),
            "name": f"{product_match.get('brand', '')} {product_match.get('product_name', '')}".strip(),
            "quantity": product_match.get("serving_unit", "1 serving"),
            "serving_qty": 1.0,
        }]
        source_type    = product_match.get("source", "barcode_database")
        accuracy_level = "verified"
        confidence     = 0.98
        verified       = True
        food_quality   = product_match.get("food_quality", food_quality)

    elif label_parsed:
        nutrition      = dict(label_parsed)
        source_type    = "nutrition_label_ocr"
        accuracy_level = "verified"
        confidence     = 0.95
        verified       = True
        detected_foods = [{"id": "label_item", "name": "Packaged Food (Nutrition Label)",
                           "quantity": "1 serving", "serving_qty": 1.0}]

    else:
        return jsonify({"success": False,
                        "error": "No verified nutrition data in this session. "
                                 "Please scan barcode or nutrition label."}), 422

    # Apply any manual corrections from payload
    corrections = payload.get("corrections") or {}
    if corrections:
        for field_name in ("calories_kcal", "protein_g", "carbs_g", "fat_g",
                           "fiber_g", "sugar_g", "sodium_mg"):
            if field_name in corrections:
                try:
                    nutrition[field_name] = float(corrections[field_name])
                except (ValueError, TypeError):
                    pass
        source_type    = "user_corrected"
        accuracy_level = "user_corrected"

    # Validate
    validation = validate_nutrition(nutrition)
    if not validation["valid"]:
        return jsonify({
            "success": False,
            "error": "Nutrition data failed validation.",
            "validation_errors": validation["errors"],
        }), 422

    nutrition = sanitize_nutrition(nutrition)

    scan_data = {
        "date":           date.today().isoformat(),
        "meal_type":      meal_type,
        "detected_foods": detected_foods,
        "nutrition":      nutrition,
        "food_quality":   food_quality,
        "source":         source_type,
        "source_type":    source_type,
        "accuracy_level": accuracy_level,
        "confidence":     confidence,
        "verified":       verified,
        "validation_warnings": validation.get("warnings", []),
        "session_id":     session_id,
    }

    try:
        scan_id = save_scan(user_id, scan_data)
        _sess.close_session(session_id)
        return jsonify({
            "success": True,
            "message": "Food successfully logged.",
            "scan_id": scan_id,
            "validation_warnings": validation.get("warnings", []),
        }), 201
    except Exception as exc:
        logger.exception("Failed to save session scan: %s", exc)
        return jsonify({"success": False, "error": "Could not save food log."}), 500


# ── MANUAL NUTRITION ENTRY & CUSTOM FOOD LIBRARY ──────────────────────

_MEAL_TYPES = {"breakfast", "lunch", "snack", "dinner"}

_USER_ENTERED_QUALITY = {
    "classification": "user_entered",
    "processing_level": "unknown",
    "reasons": ["Values entered by you — not machine-verified."],
}


def _normalize_meal_type(value: Any) -> str:
    """Coerce an arbitrary meal-type value to a supported one (default lunch)."""
    meal_type = str(value or "lunch").strip().lower()
    return meal_type if meal_type in _MEAL_TYPES else "lunch"


@nutrition_bp.route("/manual", methods=["POST"])
@login_required
def manual_entry() -> Any:
    """
    Save a user-supplied food record (no image, no AI involved).

    Body (JSON):
      {
        "food_name": "Home-cooked rice",
        "meal_type": "lunch",
        "nutrition": {"calories_kcal": 200, "protein_g": 4, "carbs_g": 42, "fat_g": 1},
        "portion": {"amount": 150, "unit": "g"},
        "notes": "optional",
        "save_to_library": false
      }

    The supplied nutrition values are treated as the TOTAL for the stated
    portion — they are deliberately NOT rescaled. Records are stored with
    accuracy_level "user_entered" so the UI never presents them as verified.
    """
    user_id = str(session["user_id"])
    payload = request.get_json(silent=True) or {}

    food_name = str(payload.get("food_name") or "").strip()
    if not food_name:
        return jsonify({"success": False, "error": "food_name is required."}), 400

    raw_nutrition = payload.get("nutrition")
    if not isinstance(raw_nutrition, dict) or not raw_nutrition:
        return jsonify({"success": False, "error": "nutrition values are required."}), 400

    # Hard-reject impossible values rather than silently clamping them to the
    # valid range — clamping would make fabricated input look accepted.
    validation = validate_nutrition(raw_nutrition)
    if not validation["valid"]:
        return jsonify({
            "success": False,
            "error": "Nutrition values failed validation.",
            "validation_errors": validation["errors"],
        }), 422

    nutrition = sanitize_nutrition(raw_nutrition)

    portion = payload.get("portion") or {}
    try:
        amount = float(portion.get("amount") or 1)
    except (TypeError, ValueError):
        amount = 1.0
    amount = max(0.1, round(amount, 2))
    unit = str(portion.get("unit") or "serving").strip() or "serving"

    nutrition["serving_qty"] = amount
    nutrition["serving_unit"] = unit

    scan_data = {
        "date": payload.get("date") or date.today().isoformat(),
        "meal_type": _normalize_meal_type(payload.get("meal_type")),
        "detected_foods": [{
            "id": "manual_entry",
            "name": food_name,
            "quantity": f"{amount:g} {unit}",
            "serving_qty": amount,
            "serving_unit": unit,
            "confidence": 1.0,
        }],
        "nutrition": nutrition,
        "food_quality": _USER_ENTERED_QUALITY,
        "source": "user_input",
        "source_type": "user_input",
        "accuracy_level": "user_entered",
        "confidence": 1.0,
        "verified": False,
        "serving_size_g": (
            amount if unit.lower() in {"g", "gram", "grams", "ml"} else None
        ),
        "notes": str(payload.get("notes") or ""),
        "validation_warnings": validation.get("warnings", []),
    }

    try:
        scan_id = save_scan(user_id, scan_data)
    except Exception as exc:
        logger.exception("Failed to save manual food record: %s", exc)
        return jsonify({"success": False, "error": "Could not save food record."}), 500

    response: dict[str, Any] = {
        "success": True,
        "message": "Food saved to today's nutrition.",
        "scan_id": scan_id,
        "validation_warnings": validation.get("warnings", []),
    }

    # Optionally remember this food for one-click re-entry later.
    if payload.get("save_to_library"):
        try:
            response["custom_food_id"] = save_custom_food(user_id, {
                "name": food_name,
                "nutrition": nutrition,
                "portion": {"amount": amount, "unit": unit},
                "food_quality": _USER_ENTERED_QUALITY,
            })
        except Exception as exc:
            logger.warning("Could not save custom food %r: %s", food_name, exc)

    return jsonify(response), 201


@nutrition_bp.route("/my-foods", methods=["GET"])
@login_required
def get_my_foods() -> Any:
    """List the user's saved custom foods, most recently used first."""
    user_id = str(session["user_id"])
    try:
        return jsonify({"success": True, "data": list_custom_foods(user_id)}), 200
    except Exception as exc:
        logger.exception("Could not list custom foods: %s", exc)
        return jsonify({
            "success": False,
            "error": "Could not load your saved foods.",
        }), 500


@nutrition_bp.route("/my-foods/<food_id>", methods=["DELETE"])
@login_required
def remove_my_food(food_id: str) -> Any:
    """Delete one saved custom food owned by the current user."""
    user_id = str(session["user_id"])
    if delete_custom_food(user_id, food_id):
        return jsonify({"success": True, "message": "Saved food removed."}), 200
    return jsonify({"success": False, "error": "Saved food not found."}), 404


@nutrition_bp.route("/product-search", methods=["GET"])
@login_required
def product_search() -> Any:
    """
    Search Open Food Facts by product name for user selection.
    Query: ?q=amul gold milk&limit=5
    """
    query = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 5)), 10)

    if not query:
        return jsonify({"success": False, "error": "Query string required."}), 400

    svc = get_product_lookup_service()
    try:
        results = svc.search_by_name(query, limit=limit)
        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in results],
        }), 200
    except Exception as exc:
        logger.exception("Product search failed: %s", exc)
        return jsonify({"success": False, "error": "Product search temporarily unavailable."}), 503
