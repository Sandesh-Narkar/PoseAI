"""
core/exercise_data.py
----------------------
Static exercise reference data for PoseAI.

This module stores all exercise metadata consumed by the UI layer
(guide panel image, target muscles, difficulty, goal reps, number of
sets, and step instructions). It contains no logic and no external
dependencies - keeping it a pure data module makes it trivial to
extend with new exercises or load from an external source later
without touching any workout or rendering code.

Keys correspond to the same workout-selection keys used throughout
the application (see main.py's `self.workouts` dispatch table).
"""

from typing import Dict, List, TypedDict


class ExerciseInfo(TypedDict):
    """Shape of a single exercise's metadata entry."""

    name: str
    image: str
    target: str
    difficulty: str
    goal: int
    sets: int
    instructions: List[str]


# ---------------------------------------------------------------------------
# Exercise metadata registry
# ---------------------------------------------------------------------------
# Keyed by the same short identifiers used to select workouts elsewhere
# in the app (matches main.py's WorkoutApp.workouts keys).
EXERCISE_DATA: Dict[str, ExerciseInfo] = {
    "1": {
        "name": "Bicep Curl",
        "image": "bicep_curl.png",
        "target": "Biceps",
        "difficulty": "Easy",
        "goal": 15,
        "sets": 3,
        "instructions": [
            "Stand straight with elbows close to your torso.",
            "Curl the weight up toward your shoulder.",
            "Squeeze your bicep at the top of the movement.",
            "Lower slowly back to the starting position.",
        ],
    },
    "2": {
        "name": "Push-up",
        "image": "pushup.png",
        "target": "Chest / Triceps",
        "difficulty": "Intermediate",
        "goal": 12,
        "sets": 3,
        "instructions": [
            "Place hands slightly wider than shoulder-width.",
            "Keep your body in a straight line head to heel.",
            "Lower your chest until elbows reach about 90 degrees.",
            "Press back up without flaring your elbows.",
        ],
    },
    "3": {
        "name": "Squat",
        "image": "squat.png",
        "target": "Quads / Glutes",
        "difficulty": "Beginner",
        "goal": 15,
        "sets": 3,
        "instructions": [
            "Stand with feet shoulder-width apart, toes slightly out.",
            "Push your hips back and bend your knees to descend.",
            "Keep your chest up and back flat as you lower.",
            "Drive through your heels to stand back up.",
        ],
    },
    "4": {
        "name": "Triceps Pushdown",
        "image": "triceps_pushdown.png",
        "target": "Triceps",
        "difficulty": "Easy",
        "goal": 15,
        "sets": 3,
        "instructions": [
            "Keep your elbows pinned close to your torso.",
            "Push the weight down until your arms are straight.",
            "Squeeze your triceps at full extension.",
            "Slowly return to the starting bent-elbow position.",
        ],
    },
    "5": {
        "name": "Lunges",
        "image": "lunges.png",
        "target": "Quads / Glutes / Hamstrings",
        "difficulty": "Intermediate",
        "goal": 12,
        "sets": 3,
        "instructions": [
            "Step forward with one leg, keeping your torso upright.",
            "Lower until both knees reach roughly 90 degrees.",
            "Keep your front knee aligned over your ankle.",
            "Push back through your front heel to return to standing.",
        ],
    },
    "6": {
        "name": "Jumping Jacks",
        "image": "jumping_jacks.png",
        "target": "Full Body / Cardio",
        "difficulty": "Easy",
        "goal": 20,
        "sets": 3,
        "instructions": [
            "Start standing with feet together and arms at your sides.",
            "Jump while spreading your legs and raising your arms overhead.",
            "Jump again to return to the starting position.",
            "Keep a steady, rhythmic pace throughout.",
        ],
    },
    "7": {
        "name": "Shoulder Press",
        "image": "shoulder_press.png",
        "target": "Shoulders / Triceps",
        "difficulty": "Intermediate",
        "goal": 12,
        "sets": 3,
        "instructions": [
            "Start with elbows bent and hands at shoulder height.",
            "Press both arms straight up overhead.",
            "Fully extend without locking your elbows harshly.",
            "Lower back down to shoulder height with control.",
        ],
    },
    "8": {
        "name": "Burpees",
        "image": "burpees.png",
        "target": "Full Body / Cardio",
        "difficulty": "Advanced",
        "goal": 10,
        "sets": 3,
        "instructions": [
            "Drop into a squat and place your hands on the floor.",
            "Kick your feet back into a plank position.",
            "Jump your feet back toward your hands.",
            "Explode upward into a jump to finish the rep.",
        ],
    },
    "9": {
        "name": "Warrior II",
        "image": "warrior2.png",
        "target": "Legs / Core / Balance",
        "difficulty": "Intermediate",
        "goal": 8,
        "sets": 2,
        "instructions": [
            "Step your feet wide apart, front foot pointing forward.",
            "Bend your front knee to roughly 90 degrees.",
            "Extend both arms parallel to the floor.",
            "Hold the pose while keeping your torso upright.",
        ],
    },
    "g": {
        "name": "Goblet Squat",
        "image": "goblet_squat.png",
        "target": "Quads / Glutes / Core",
        "difficulty": "Intermediate",
        "goal": 12,
        "sets": 3,
        "instructions": [
            "Hold a weight close to your chest with both hands.",
            "Stand with feet shoulder-width apart, toes slightly out.",
            "Squat down while keeping your chest up and elbows inside your knees.",
            "Drive through your heels to return to standing.",
        ],
    },
    "t": {
        "name": "Crossover Toe Touches",
        "image": "crossover_toe_touch.png",
        "target": "Core / Obliques",
        "difficulty": "Beginner",
        "goal": 15,
        "sets": 3,
        "instructions": [
            "Stand tall with feet shoulder-width apart.",
            "Rotate your torso and reach across your body.",
            "Touch the opposite side with a straight arm.",
            "Return to center with control, then switch sides.",
        ],
    },
}


def get_exercise_info(key: str) -> ExerciseInfo:
    """
    Retrieve exercise metadata by its short selection key (e.g. "1",
    "g", "t"). Falls back to a safe generic entry if the key is
    unrecognized, so calling code never has to special-case a missing
    lookup.
    """
    return EXERCISE_DATA.get(key, _DEFAULT_EXERCISE_INFO)


def get_exercise_info_by_name(name: str) -> ExerciseInfo:
    """
    Retrieve exercise metadata by its display name (e.g. "Squat").
    Falls back to a safe generic entry if no exercise matches.
    """
    for info in EXERCISE_DATA.values():
        if info["name"] == name:
            return info
    return _DEFAULT_EXERCISE_INFO


# Generic fallback used when a lookup key/name isn't found in the
# registry, so callers always receive a well-formed ExerciseInfo.
_DEFAULT_EXERCISE_INFO: ExerciseInfo = {
    "name": "Unknown Exercise",
    "image": "default.png",
    "target": "Full Body",
    "difficulty": "N/A",
    "goal": 10,
    "sets": 1,
    "instructions": [
        "Maintain good posture throughout.",
        "Move with slow, controlled motion.",
        "Breathe steadily during the movement.",
        "Stop immediately if you feel sharp pain.",
    ],
}