"""
PoseAI Nutrition Intelligence System — Service Layer
====================================================
Business logic for:
1. Target calculation from real user profile and goals (Mifflin-St Jeor)
2. Daily nutrition aggregation & meal timeline management
3. Data-grounded AI Daily Insights (combining food + workout metrics)
4. "You Ate It. Let's Get Active" exercise recommendations connecting
   to real PoseAI workout exercises
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from database.mongo import find_user_by_id
from nutrition.repository import (
    get_daily_nutrition,
    get_scans_by_date,
    recalculate_daily_nutrition,
)
from database.workouts import get_workouts_collection

logger = logging.getLogger("poseai.nutrition.service")


def calculate_user_targets(user_id: str) -> dict[str, Any]:
    """
    Calculate personalized nutrition targets based strictly on user profile data.
    If the user has not completed their profile, returns unconfigured status
    with prompt to configure profile rather than inventing personalized numbers.
    """
    try:
        user_doc = find_user_by_id(user_id)
    except Exception as e:
        logger.warning("Could not fetch user profile for targets: %s", e)
        user_doc = None

    if not user_doc:
        return {
            "configured": False,
            "message": "Set your fitness profile to personalize nutrition targets.",
            "calories_kcal": None,
            "protein_g": None,
            "carbs_g": None,
            "fat_g": None,
            "fiber_g": None,
        }

    weight = user_doc.get("weight")
    height = user_doc.get("height")
    age = user_doc.get("age")
    fitness_goal = (user_doc.get("fitness_goal") or "").strip()
    gender = (user_doc.get("gender") or "Prefer not to say").strip().lower()

    # If critical fields are missing, do NOT invent personalized numbers
    if not weight or not height or not age or not fitness_goal:
        return {
            "configured": False,
            "message": "Set your fitness profile to personalize nutrition targets.",
            "calories_kcal": None,
            "protein_g": None,
            "carbs_g": None,
            "fat_g": None,
            "fiber_g": None,
        }

    try:
        w_kg = float(weight)
        h_cm = float(height)
        a_yr = float(age)
    except (ValueError, TypeError):
        return {
            "configured": False,
            "message": "Set your fitness profile to personalize nutrition targets.",
            "calories_kcal": None,
            "protein_g": None,
            "carbs_g": None,
            "fat_g": None,
            "fiber_g": None,
        }

    # 1. Base BMR via Mifflin-St Jeor Formula
    if "female" in gender:
        bmr = 10.0 * w_kg + 6.25 * h_cm - 5.0 * a_yr - 161.0
    elif "male" in gender:
        bmr = 10.0 * w_kg + 6.25 * h_cm - 5.0 * a_yr + 5.0
    else:
        # Neutral average
        bmr = 10.0 * w_kg + 6.25 * h_cm - 5.0 * a_yr - 78.0

    # 2. Activity Multiplier based on weekly goal or experience
    weekly_workouts = user_doc.get("weekly_workout_goal")
    try:
        ww = int(weekly_workouts) if weekly_workouts else 3
    except (ValueError, TypeError):
        ww = 3

    if ww >= 5:
        activity_multiplier = 1.6
    elif ww >= 3:
        activity_multiplier = 1.45
    elif ww >= 1:
        activity_multiplier = 1.3
    else:
        activity_multiplier = 1.2

    tdee = bmr * activity_multiplier

    # 3. Goal Macro Adjustments
    goal_lower = fitness_goal.lower()
    if "lose weight" in goal_lower:
        target_calories = max(1350, int(round(tdee - 450)))
        p_pct, c_pct, f_pct = 0.30, 0.40, 0.30
        fiber = 30
    elif "gain weight" in goal_lower or "improve strength" in goal_lower:
        target_calories = int(round(tdee + 350))
        p_pct, c_pct, f_pct = 0.28, 0.50, 0.22
        fiber = 32
    else:
        # Maintain weight / general fitness
        target_calories = int(round(tdee))
        p_pct, c_pct, f_pct = 0.25, 0.50, 0.25
        fiber = 28

    protein_g = int(round((target_calories * p_pct) / 4.0))
    carbs_g = int(round((target_calories * c_pct) / 4.0))
    fat_g = int(round((target_calories * f_pct) / 9.0))

    return {
        "configured": True,
        "fitness_goal": fitness_goal,
        "calories_kcal": target_calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "fiber_g": fiber,
    }


def generate_daily_insight(
    totals: dict[str, Any],
    targets: dict[str, Any],
    activity: dict[str, Any],
    today_workouts: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Generate dynamic, supportive, data-grounded AI daily insight.
    Synthesizes real food intake with actual completed PoseAI workouts.
    """
    cal_eaten = totals.get("calories_kcal", 0)
    prot_eaten = totals.get("protein_g", 0.0)
    carbs_eaten = totals.get("carbs_g", 0.0)
    fat_eaten = totals.get("fat_g", 0.0)

    target_cal = targets.get("calories_kcal")
    target_prot = targets.get("protein_g")

    workout_kcal = activity.get("estimated_workout_kcal", 0)
    workout_count = activity.get("workout_count", 0)

    observations = []
    recommendations = []

    # If no data logged yet
    if cal_eaten == 0 and workout_count == 0:
        return {
            "summary": "Start logging your meals today to unlock personalized nutrition analysis and energy balance insights.",
            "observations": ["No meals logged yet today.", "No workout activity recorded yet."],
            "recommendations": ["Use 'Scan Food' or 'Upload Food Image' to log your first meal."],
            "confidence": "Data-grounded",
        }

    # Summary synthesis
    summary_parts = []
    if target_prot and prot_eaten > 0:
        summary_parts.append(
            f"Your recorded protein intake is currently {int(round(prot_eaten))}g against your selected {target_prot}g target."
        )
    elif prot_eaten > 0:
        summary_parts.append(f"You have recorded {int(round(prot_eaten))}g of protein today.")

    if workout_count > 0:
        exercises_done = list({w.get("exercise", "workout").replace("_", " ").title() for w in today_workouts})
        ex_str = ", ".join(exercises_done[:2])
        summary_parts.append(
            f"You also completed {workout_count} workout session{'s' if workout_count > 1 else ''} ({ex_str}) burning an estimated {workout_kcal} kcal."
        )
    else:
        summary_parts.append("No workout session has been recorded yet today.")

    if target_prot and prot_eaten < (target_prot * 0.7):
        if workout_count > 0:
            summary_parts.append(
                "A protein-rich meal (such as paneer, dal, eggs, or chicken) could help support muscle recovery toward your selected target."
            )
        else:
            summary_parts.append("Consider incorporating a protein-dense food in your next meal to progress toward your target.")
    elif target_prot and prot_eaten >= target_prot:
        summary_parts.append("Great job meeting your daily protein objective!")

    summary = " ".join(summary_parts)

    # Observations
    if cal_eaten > 0:
        observations.append(f"Recorded energy intake: {cal_eaten:,} kcal across today's meals.")
    if workout_kcal > 0:
        observations.append(f"Recorded activity expenditure: {workout_kcal:,} estimated kcal.")
        net = cal_eaten - workout_kcal
        observations.append(f"Net recorded energy: {net:,} kcal.")

    if target_cal:
        pct_cal = int(round((cal_eaten / target_cal) * 100))
        observations.append(f"Caloric pacing: {pct_cal}% of target reached.")

    # Recommendations
    if workout_count == 0 and cal_eaten > 0:
        recommendations.append("A quick 10-minute PoseAI bodyweight session would stimulate metabolic rate.")
    if prot_eaten < 50 and cal_eaten > 800:
        recommendations.append("Incorporate whole food proteins (lentils, yogurt, eggs, or cottage cheese) to enhance satiety.")
    if totals.get("fiber_g", 0) < 15 and cal_eaten > 600:
        recommendations.append("Include fresh vegetables or whole grains to increase dietary fiber.")

    if not recommendations:
        recommendations.append("Maintain steady hydration and continue logging your remaining meals.")

    return {
        "summary": summary,
        "observations": observations,
        "recommendations": recommendations,
        "confidence": "Data-grounded",
    }


def suggest_exercise_for_recent_food(
    scans: list[dict[str, Any]],
    user_id: str,
) -> dict[str, Any]:
    """
    'You Ate It. Let's Get Active'
    Suggests a real PoseAI exercise based on recently consumed food.
    CRITICAL: Never framed as punishment; always an empowering invitation to move.
    """
    latest_food_name = "your last meal"
    estimated_kcal = 230
    serving_info = ""

    if scans:
        latest_scan = scans[-1]
        foods = latest_scan.get("detected_foods", [])
        if foods:
            latest_food_name = foods[0].get("name", "your meal")
            serving_info = foods[0].get("quantity", "")
        nutrition = latest_scan.get("nutrition", {})
        estimated_kcal = int(nutrition.get("calories_kcal", 230) or 230)

    # Existing exercises supported by PoseAI CV engine
    candidate_exercises = [
        {
            "id": "squat",
            "name": "Squats",
            "subtitle": "Lower body strength & power",
            "suggested_sets": 3,
            "suggested_reps": 15,
            "estimated_burn_rate_kcal_min": 8.0,
            "icon": "fitness_center",
        },
        {
            "id": "jumping_jacks",
            "name": "Jumping Jacks",
            "subtitle": "Full body cardio & conditioning",
            "suggested_sets": 3,
            "suggested_reps": 25,
            "estimated_burn_rate_kcal_min": 9.5,
            "icon": "directions_run",
        },
        {
            "id": "pushup",
            "name": "Pushups",
            "subtitle": "Chest, shoulders & core",
            "suggested_sets": 3,
            "suggested_reps": 12,
            "estimated_burn_rate_kcal_min": 7.5,
            "icon": "sports_gymnastics",
        },
        {
            "id": "lunges",
            "name": "Lunges",
            "subtitle": "Leg endurance & stability",
            "suggested_sets": 3,
            "suggested_reps": 12,
            "estimated_burn_rate_kcal_min": 7.0,
            "icon": "directions_walk",
        },
    ]

    # Select exercise matching calorie magnitude
    if estimated_kcal > 400:
        chosen = candidate_exercises[1]  # Jumping jacks or squats
    else:
        chosen = candidate_exercises[0]  # Squats

    return {
        "recent_food": latest_food_name,
        "serving_info": serving_info,
        "estimated_kcal": estimated_kcal,
        "headline": f"Recently recorded: {latest_food_name} (≈ {estimated_kcal} kcal estimated)",
        "prompt": "Want to add some invigorating activity today?",
        "suggested_exercise": {
            "id": chosen["id"],
            "name": chosen["name"],
            "subtitle": chosen["subtitle"],
            "routine": f"{chosen['suggested_sets']} sets × {chosen['suggested_reps']} reps",
            "start_url": f"/workout?exercise={chosen['id']}",
        },
    }


def get_today_nutrition_dashboard(user_id: str) -> dict[str, Any]:
    """
    Complete dashboard payload for the Nutrition page.
    Assembles totals, targets, energy balance, meal timeline, food quality,
    AI daily insight, and activity recommendations.
    """
    today_str = date.today().isoformat()
    uid = str(user_id)

    # 1. Calculate targets
    targets = calculate_user_targets(uid)

    # 2. Recalculate/get today's daily record
    daily = recalculate_daily_nutrition(uid, today_str, targets if targets["configured"] else None)

    # 3. Retrieve all scans for today
    scans = get_scans_by_date(uid, today_str)

    # 4. Group scans by meal timeline
    meal_timeline = {
        "breakfast": [],
        "lunch": [],
        "snack": [],
        "dinner": [],
    }
    for s in scans:
        m_type = (s.get("meal_type") or "lunch").lower()
        if m_type not in meal_timeline:
            meal_timeline[m_type] = []
        meal_timeline[m_type].append(s)

    # 5. Fetch today's workout sessions
    workout_coll = get_workouts_collection()
    today_workouts = list(workout_coll.find({"user_id": uid, "date": today_str}))

    # 6. Generate AI Daily Insight
    insight = generate_daily_insight(
        daily.get("totals", {}),
        targets,
        daily.get("activity", {}),
        today_workouts,
    )

    # 7. Generate 'You Ate It. Let's Get Active' suggestion
    activity_suggestion = suggest_exercise_for_recent_food(scans, uid)

    # 8. Assemble Energy Balance
    eaten = daily.get("totals", {}).get("calories_kcal", 0)
    workout_burn = daily.get("activity", {}).get("estimated_workout_kcal", 0)
    net_recorded = eaten - workout_burn

    energy_balance = {
        "eaten_kcal": eaten,
        "activity_kcal": workout_burn,
        "net_recorded_kcal": net_recorded,
        "label": "Net recorded energy",
        "description": "Not your exact metabolic balance; basal metabolism, digestion, and general movement are not represented.",
    }

    return {
        "date": today_str,
        "totals": daily.get("totals", {}),
        "targets": targets,
        "energy_balance": energy_balance,
        "food_quality": daily.get("food_quality", {}),
        "meal_timeline": meal_timeline,
        "meal_count": len([m for m in meal_timeline.values() if m]),
        "scan_count": len(scans),
        "activity": daily.get("activity", {}),
        "daily_insight": insight,
        "activity_suggestion": activity_suggestion,
    }
