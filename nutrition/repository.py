"""
PoseAI Nutrition Intelligence System — Database Repository Layer
================================================================
Handles MongoDB collections for `nutrition_scans` and `daily_nutrition`.
Ensures atomic and idempotent daily aggregations, user isolation, and
seamless integration with `workout_sessions`.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from database import mongo as mongo_db
from database.workouts import get_workouts_collection

logger = logging.getLogger("poseai.nutrition.repository")

_INDEXES_ENSURED = False


def _ensure_indexes(database: Any) -> None:
    """Ensure indexes on nutrition collections (best effort)."""
    try:
        database["nutrition_scans"].create_index(
            [("user_id", ASCENDING), ("date", ASCENDING), ("created_at", DESCENDING)]
        )
        database["daily_nutrition"].create_index(
            [("user_id", ASCENDING), ("date", ASCENDING)], unique=True
        )
        database["custom_foods"].create_index(
            [("user_id", ASCENDING), ("name_lower", ASCENDING)], unique=True
        )
    except Exception as e:
        logger.warning("Could not create nutrition indexes: %s", e)


def _db() -> Any:
    global _INDEXES_ENSURED
    database = mongo_db.get_db()
    if not _INDEXES_ENSURED:
        _ensure_indexes(database)
        _INDEXES_ENSURED = True
    return database


def get_scans_collection() -> Any:
    return _db()["nutrition_scans"]


def get_daily_collection() -> Any:
    return _db()["daily_nutrition"]


def get_custom_foods_collection() -> Any:
    """Per-user saved food templates (manual entry library)."""
    return _db()["custom_foods"]


def _clean_user_id(user_id: Any) -> str:
    """Normalize user_id to string representation."""
    return str(user_id)


def save_scan(user_id: str, scan_data: dict[str, Any]) -> str:
    """
    Insert a confirmed food scan record for the user.
    Returns the inserted document ID as a string.
    """
    coll = get_scans_collection()
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": _clean_user_id(user_id),
        "date": scan_data.get("date") or date.today().isoformat(),
        "meal_type": (scan_data.get("meal_type") or "lunch").lower(),
        "image_reference": scan_data.get("image_reference", ""),
        "detected_foods": scan_data.get("detected_foods", []),
        "nutrition": scan_data.get("nutrition", {}),
        "food_quality": scan_data.get("food_quality", {}),
        "source": scan_data.get("source", "barcode_database"),
        "source_type": scan_data.get("source_type") or scan_data.get("source", "barcode_database"),
        "accuracy_level": scan_data.get("accuracy_level", "LEVEL 1 — VERIFIED"),
        "original_result": scan_data.get("original_result"),
        "corrected_result": scan_data.get("corrected_result"),
        "serving_size_g": scan_data.get("serving_size_g"),
        "confidence": float(scan_data.get("confidence", 0.95)),
        "notes": scan_data.get("notes", ""),
        "created_at": now,
        "updated_at": now,
    }
    result = coll.insert_one(doc)
    scan_id = str(result.inserted_id)

    # Automatically recompute daily totals
    recalculate_daily_nutrition(user_id, doc["date"])
    return scan_id


def get_scans_by_date(user_id: str, date_str: str) -> list[dict[str, Any]]:
    """Retrieve all scans for a user on a given date string (YYYY-MM-DD)."""
    coll = get_scans_collection()
    cursor = coll.find(
        {"user_id": _clean_user_id(user_id), "date": date_str}
    ).sort("created_at", ASCENDING)

    results = []
    for item in cursor:
        item["id"] = str(item.pop("_id"))
        results.append(item)
    return results


def get_scan_by_id(user_id: str, scan_id: str) -> Optional[dict[str, Any]]:
    """Retrieve a single scan belonging to user_id."""
    try:
        oid = ObjectId(scan_id)
    except Exception:
        return None

    coll = get_scans_collection()
    doc = coll.find_one({"_id": oid, "user_id": _clean_user_id(user_id)})
    if not doc:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


def update_scan(user_id: str, scan_id: str, updates: dict[str, Any]) -> bool:
    """Update meal type, portion, or nutrition of a scan."""
    try:
        oid = ObjectId(scan_id)
    except Exception:
        return False

    coll = get_scans_collection()
    clean_updates = dict(updates)
    clean_updates["updated_at"] = datetime.now(timezone.utc)
    clean_updates.pop("_id", None)
    clean_updates.pop("user_id", None)

    res = coll.update_one(
        {"_id": oid, "user_id": _clean_user_id(user_id)},
        {"$set": clean_updates},
    )
    if res.matched_count > 0:
        # Re-fetch doc to trigger daily recalculation
        doc = coll.find_one({"_id": oid})
        if doc and "date" in doc:
            recalculate_daily_nutrition(user_id, doc["date"])
        return True
    return False


def delete_scan(user_id: str, scan_id: str) -> bool:
    """Delete a scan and recalculate daily nutrition."""
    try:
        oid = ObjectId(scan_id)
    except Exception:
        return False

    coll = get_scans_collection()
    doc = coll.find_one({"_id": oid, "user_id": _clean_user_id(user_id)})
    if not doc:
        return False

    target_date = doc.get("date", date.today().isoformat())
    res = coll.delete_one({"_id": oid, "user_id": _clean_user_id(user_id)})
    if res.deleted_count > 0:
        recalculate_daily_nutrition(user_id, target_date)
        return True
    return False


def recalculate_daily_nutrition(
    user_id: str,
    date_str: str,
    targets: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Idempotently calculate and persist daily nutrition aggregates:
    - Sums all scans for `user_id` on `date_str`
    - Computes macro totals and food quality distribution
    - Pulls actual workout sessions from `workout_sessions` collection for `date_str`
    - Updates `daily_nutrition` collection
    """
    uid = _clean_user_id(user_id)
    scans_coll = get_scans_collection()
    daily_coll = get_daily_collection()

    scans = list(scans_coll.find({"user_id": uid, "date": date_str}))

    # Aggregate nutrition totals
    cal_sum = 0
    prot_sum = 0.0
    carbs_sum = 0.0
    fat_sum = 0.0
    fiber_sum = 0.0
    sugar_sum = 0.0
    sodium_sum = 0

    meal_types_seen = set()
    nutrient_dense_count = 0
    occasional_count = 0

    for s in scans:
        nut = s.get("nutrition", {})
        cal_sum += int(nut.get("calories_kcal", 0) or 0)
        prot_sum += float(nut.get("protein_g", 0.0) or 0.0)
        carbs_sum += float(nut.get("carbs_g", 0.0) or 0.0)
        fat_sum += float(nut.get("fat_g", 0.0) or 0.0)
        fiber_sum += float(nut.get("fiber_g", 0.0) or 0.0)
        sugar_sum += float(nut.get("sugar_g", 0.0) or 0.0)
        sodium_sum += int(nut.get("sodium_mg", 0) or 0)

        mt = s.get("meal_type")
        if mt:
            meal_types_seen.add(mt.lower())

        fq = s.get("food_quality", {})
        if fq.get("classification") == "occasional":
            occasional_count += 1
        else:
            nutrient_dense_count += 1

    total_scans = len(scans)
    if total_scans > 0:
        nd_pct = int(round((nutrient_dense_count / total_scans) * 100))
        occ_pct = 100 - nd_pct
    else:
        nd_pct = 0
        occ_pct = 0

    # Query real workouts for the day
    workout_coll = get_workouts_collection()
    workouts = list(workout_coll.find({"user_id": uid, "date": date_str}))
    workout_kcal = sum(float(w.get("calories", 0.0) or 0.0) for w in workouts)
    workout_count = len(workouts)

    totals = {
        "calories_kcal": cal_sum,
        "protein_g": round(prot_sum, 1),
        "carbs_g": round(carbs_sum, 1),
        "fat_g": round(fat_sum, 1),
        "fiber_g": round(fiber_sum, 1),
        "sugar_g": round(sugar_sum, 1),
        "sodium_mg": sodium_sum,
    }

    food_quality = {
        "nutrient_dense_percentage": nd_pct,
        "occasional_percentage": occ_pct,
        "nutrient_dense_count": nutrient_dense_count,
        "occasional_count": occasional_count,
    }

    activity = {
        "estimated_workout_kcal": int(round(workout_kcal)),
        "workout_count": workout_count,
    }

    doc = {
        "user_id": uid,
        "date": date_str,
        "totals": totals,
        "meal_count": len(meal_types_seen),
        "scan_count": total_scans,
        "food_quality": food_quality,
        "activity": activity,
        "updated_at": datetime.now(timezone.utc),
    }
    if targets:
        doc["targets"] = targets

    daily_coll.update_one(
        {"user_id": uid, "date": date_str},
        {"$set": doc},
        upsert=True,
    )

    doc["net_recorded_energy_kcal"] = totals["calories_kcal"] - activity["estimated_workout_kcal"]
    return doc


def get_daily_nutrition(user_id: str, date_str: str) -> dict[str, Any]:
    """
    Fetch stored daily nutrition, recalculating if not yet recorded.
    """
    uid = _clean_user_id(user_id)
    daily_coll = get_daily_collection()
    doc = daily_coll.find_one({"user_id": uid, "date": date_str})
    if not doc:
        return recalculate_daily_nutrition(user_id, date_str)

    doc.pop("_id", None)
    # Ensure net energy is populated
    totals = doc.get("totals", {})
    act = doc.get("activity", {})
    doc["net_recorded_energy_kcal"] = (
        totals.get("calories_kcal", 0) - act.get("estimated_workout_kcal", 0)
    )
    return doc


def get_nutrition_history(user_id: str, days: int = 7) -> list[dict[str, Any]]:
    """
    Retrieve nutrition day records for the past `days` days.
    Guarantees ordered chronological series.
    """
    uid = _clean_user_id(user_id)
    today = date.today()
    start_date = (today - timedelta(days=days - 1)).isoformat()
    end_date = today.isoformat()

    daily_coll = get_daily_collection()
    cursor = daily_coll.find(
        {"user_id": uid, "date": {"$gte": start_date, "$lte": end_date}}
    ).sort("date", ASCENDING)

    records_by_date = {r["date"]: r for r in cursor}

    history: list[dict[str, Any]] = []
    for i in range(days):
        d_str = (today - timedelta(days=(days - 1 - i))).isoformat()
        rec = records_by_date.get(d_str)
        if rec:
            rec.pop("_id", None)
            history.append(rec)
        else:
            # Fallback zero record
            history.append({
                "user_id": uid,
                "date": d_str,
                "totals": {
                    "calories_kcal": 0,
                    "protein_g": 0.0,
                    "carbs_g": 0.0,
                    "fat_g": 0.0,
                    "fiber_g": 0.0,
                    "sugar_g": 0.0,
                    "sodium_mg": 0,
                },
                "meal_count": 0,
                "scan_count": 0,
                "food_quality": {
                    "nutrient_dense_percentage": 0,
                    "occasional_percentage": 0,
                },
                "activity": {
                    "estimated_workout_kcal": 0,
                    "workout_count": 0,
                },
                "net_recorded_energy_kcal": 0,
            })
    return history


# ---------------------------------------------------------------------------
# Custom foods — reusable user-entered nutrition templates ("My Foods")
# ---------------------------------------------------------------------------

def save_custom_food(user_id: str, food_data: dict[str, Any]) -> str:
    """
    Insert or update a reusable custom food for the user.

    Uniqueness is (user_id, name) — saving the same name again updates the
    existing template instead of creating a duplicate. Returns the id string.
    """
    coll = get_custom_foods_collection()
    uid = _clean_user_id(user_id)
    now = datetime.now(timezone.utc)
    name = str(food_data.get("name") or "").strip()
    name_lower = name.lower()

    doc = {
        "user_id": uid,
        "name": name,
        "name_lower": name_lower,
        "nutrition": food_data.get("nutrition", {}),
        "portion": food_data.get("portion", {}),
        "food_quality": food_data.get("food_quality", {}),
        "updated_at": now,
    }

    existing = coll.find_one({"user_id": uid, "name_lower": name_lower})
    if existing:
        coll.update_one({"_id": existing["_id"]}, {"$set": doc})
        return str(existing["_id"])

    doc["created_at"] = now
    result = coll.insert_one(doc)
    return str(result.inserted_id)


def list_custom_foods(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return the user's saved custom foods, most recently updated first."""
    coll = get_custom_foods_collection()
    cursor = coll.find(
        {"user_id": _clean_user_id(user_id)}
    ).sort("updated_at", DESCENDING).limit(limit)

    results: list[dict[str, Any]] = []
    for item in cursor:
        item["id"] = str(item.pop("_id"))
        results.append(item)
    return results


def delete_custom_food(user_id: str, food_id: str) -> bool:
    """Delete a saved custom food owned by user_id. Returns True if removed."""
    try:
        oid = ObjectId(food_id)
    except Exception:
        return False

    coll = get_custom_foods_collection()
    result = coll.delete_one({"_id": oid, "user_id": _clean_user_id(user_id)})
    return result.deleted_count > 0
