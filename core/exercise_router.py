"""
core/exercise_router.py
-----------------------
Camera-independent exercise ROUTING engine shared by BOTH input sources:

    desktop:  core.exercise_router.ExerciseRouter  + cv2 camera (main.py)
    web:      core.exercise_router.ExerciseRouter  + browser frames
              (core/web_workout_engine.py -> app.py POST /api/workout/frame)

This module is the single implementation of the per-exercise landmark
handlers. It decides, for each selected exercise, which body-part
landmarks to feed into that exercise's `update()` method (which performs
the actual angle calculation, rep counting, stage tracking and coaching
feedback). The routine used to be copy-pasted twice (once inside
WorkoutApp in main.py, once inside WebWorkoutEngine) - keeping a single
copy guarantees the desktop engine and the web engine can never drift
apart.

It performs NO camera work, NO pose detection and NO UI: it consumes the
smoothed landmark frame (the same 33-landmark dict list produced by
core/landmark_manager.py + core/landmark_smoother.py) and returns the
exercise result dict:
    {"exercise": str, "reps": int, "stage": str, "angle": float,
     "feedback": str}
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from core.landmark_manager import LandmarkManager
from workouts.bicep import BicepWorkout
from workouts.burpees import BurpeesWorkout
from workouts.crossover_toe_touch import CrossoverToeTouchWorkout
from workouts.goblet_squat import GobletSquatWorkout
from workouts.jumping_jacks import JumpingJacksWorkout
from workouts.lunges import LungesWorkout
from workouts.pushup import PushupWorkout
from workouts.shoulder_press import ShoulderPressWorkout
from workouts.squat import SquatWorkout
from workouts.triceps_pushdown import TricepsPushdownWorkout
from workouts.warrior2 import Warrior2Workout

# Minimum average visibility required on the body parts an exercise
# needs before its workout logic runs. Below this we report
# "Move Into Camera View" so the user repositions themselves.
VISIBILITY_THRESHOLD = 0.5

# Workout-selection key -> display/strokes key used by the desktop
# drawing layer (core/drawing.py) to pick the right skeleton overlay.
# Matches the workout-selection shortcuts from main.py.
EXERCISE_DRAW_KEYS: Dict[str, str] = {
    "1": "bicep_curl",
    "2": "pushup",
    "3": "squat",
    "4": "triceps_pushdown",
    "5": "lunge",
    "6": "jumping_jacks",
    "7": "shoulder_press",
    "8": "burpees",
    "9": "warrior2",
    "g": "goblet_squat",
    "t": "crossover_toe_touch",
}

# Human-friendly aliases (URL slugs / frontend labels) -> canonical key.
# The exercises page and /api/workout/start may send either the short key
# ("1") or a slug ("bicep_curl"). Both must resolve to the same engine.
EXERCISE_ALIASES: Dict[str, str] = {
    "bicep_curl": "1",
    "bicep-curl": "1",
    "bicep": "1",
    "pushup": "2",
    "push-up": "2",
    "push_up": "2",
    "squat": "3",
    "triceps_pushdown": "4",
    "triceps-pushdown": "4",
    "triceps": "4",
    "lunge": "5",
    "lunges": "5",
    "jumping_jacks": "6",
    "jumping-jacks": "6",
    "jumpingjacks": "6",
    "shoulder_press": "7",
    "shoulder-press": "7",
    "burpees": "8",
    "burpee": "8",
    "warrior2": "9",
    "warrior_2": "9",
    "warrior-2": "9",
    "warrior_ii": "9",
    "goblet_squat": "g",
    "goblet-squat": "g",
    "crossover_toe_touch": "t",
    "crossover-toe-touch": "t",
    "toe_touch": "t",
}


def normalize_exercise_key(exercise: Any) -> Optional[str]:
    """Resolve a short key, slug, or display name to the canonical key.

    Returns the canonical key ("1".."9","g","t") or None when unknown.
    Never raises — unknown values return None so callers can reject them
    with a clear error instead of silently tracking the wrong exercise.
    """
    if exercise is None:
        return None
    text = str(exercise).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in EXERCISE_DRAW_KEYS:
        return lowered
    if lowered in EXERCISE_ALIASES:
        return EXERCISE_ALIASES[lowered]
    # Display names such as "Bicep Curl" / "Push-up".
    slug = lowered.replace(" ", "_").replace("-", "_")
    if slug in EXERCISE_ALIASES:
        return EXERCISE_ALIASES[slug]
    return None

MOVE_INTO_VIEW: Dict[str, str] = {"feedback": "Move Into Camera View"}


class ExerciseRouter:
    """
    Holds the exercise registry and routes a smoothed landmark frame to
    the active workout's `update()` with the correct body-part landmarks.

    State kept here is minimal (which exercise is active, its workout
    object, a shared LandmarkManager). Reps/stage/feedback are owned by
    the individual workout objects and persist across frames; nothing in
    this router resets them.
    """

    def __init__(self) -> None:
        self.landmark_manager = LandmarkManager()

        self.workouts: Dict[str, Any] = {
            "1": BicepWorkout(),
            "2": PushupWorkout(),
            "3": SquatWorkout(),
            "4": TricepsPushdownWorkout(),
            "5": LungesWorkout(),
            "6": JumpingJacksWorkout(),
            "7": ShoulderPressWorkout(),
            "8": BurpeesWorkout(),
            "9": Warrior2Workout(),
            "g": GobletSquatWorkout(),
            "t": CrossoverToeTouchWorkout(),
        }

        # Dispatch table built once at construction instead of every frame.
        self._dispatch: Dict[str, Callable[[Any], Optional[dict]]] = {
            "1": self._run_bicep_curl,
            "2": self._run_pushup,
            "3": self._run_squat,
            "4": self._run_triceps_pushdown,
            "5": self._run_lunges,
            "6": self._run_jumping_jacks,
            "7": self._run_shoulder_press,
            "8": self._run_burpees,
            "9": self._run_warrior2,
            "g": self._run_goblet_squat,
            "t": self._run_crossover_toe_touch,
        }

        self.current_key: str = "1"
        self.active_workout: Any = self.workouts[self.current_key]

    # ------------------------------------------------------------------ #
    # SELECTION / RESET
    # ------------------------------------------------------------------ #

    def set_exercise(self, key: str) -> bool:
        """Select the workout for `key` ("1" = Bicep Curl, "bicep_curl" also works).

        Returns True if the key is known and the active workout changed,
        False for unknown keys. Does NOT reset the workout - callers that
        want a fresh rep count (a newly started session) call reset_workout().
        """
        canonical = normalize_exercise_key(key)
        workout = self.workouts.get(canonical) if canonical else None
        if workout is None:
            return False
        self.current_key = canonical
        self.active_workout = workout
        return True

    def reset_workout(self) -> None:
        """Reset the active workout's reps/stage/feedback (new session/set)."""
        self.active_workout.reset()

    def draw_key(self, key: str) -> str:
        """Return the skeleton-drawing key for a workout-selection key."""
        return EXERCISE_DRAW_KEYS.get(key, "")

    # ------------------------------------------------------------------ #
    # ROUTING
    # ------------------------------------------------------------------ #

    def run(self, landmarks) -> Optional[dict]:
        """
        Route a (smoothed, validated) landmark frame to the active
        workout's update() and return its result dict. Returns None if the
        active key has no handler (should never happen with the built-in
        registry).
        """
        handler = self._dispatch.get(self.current_key)
        if handler is None:
            return None
        return handler(landmarks)

    # ---- Arm-based exercises (best arm auto-selection) -------------------

    def _run_bicep_curl(self, landmarks):
        arm = self.landmark_manager.get_best_arm(landmarks)
        if arm["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(arm["shoulder"], arm["elbow"], arm["wrist"])
        return MOVE_INTO_VIEW

    def _run_pushup(self, landmarks):
        arm = self.landmark_manager.get_best_arm(landmarks)
        if arm["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(arm["shoulder"], arm["elbow"], arm["wrist"])
        return MOVE_INTO_VIEW

    def _run_triceps_pushdown(self, landmarks):
        arm = self.landmark_manager.get_best_arm(landmarks)
        if arm["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(arm["shoulder"], arm["elbow"], arm["wrist"])
        return MOVE_INTO_VIEW

    def _run_shoulder_press(self, landmarks):
        left_arm = self.landmark_manager.get_left_arm(landmarks)
        right_arm = self.landmark_manager.get_right_arm(landmarks)
        if left_arm["visibility"] >= VISIBILITY_THRESHOLD and right_arm["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(
                left_arm["shoulder"], left_arm["elbow"], left_arm["wrist"],
                right_arm["shoulder"], right_arm["elbow"], right_arm["wrist"],
            )
        return MOVE_INTO_VIEW

    # ---- Leg-based exercises ---------------------------------------------

    def _run_squat(self, landmarks):
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)
        if left_leg["visibility"] >= VISIBILITY_THRESHOLD and right_leg["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(
                left_leg["hip"], left_leg["knee"], left_leg["ankle"],
                right_leg["hip"], right_leg["knee"], right_leg["ankle"],
            )
        return MOVE_INTO_VIEW

    def _run_goblet_squat(self, landmarks):
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)
        if left_leg["visibility"] >= VISIBILITY_THRESHOLD and right_leg["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(
                left_leg["hip"], left_leg["knee"], left_leg["ankle"],
                right_leg["hip"], right_leg["knee"], right_leg["ankle"],
            )
        return MOVE_INTO_VIEW

    def _run_lunges(self, landmarks):
        leg = self.landmark_manager.get_best_leg(landmarks)
        if leg["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(leg["hip"], leg["knee"], leg["ankle"])
        return MOVE_INTO_VIEW

    def _run_warrior2(self, landmarks):
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)
        if left_leg["visibility"] >= VISIBILITY_THRESHOLD and right_leg["visibility"] >= VISIBILITY_THRESHOLD:
            if left_leg["knee"][1] > right_leg["knee"][1]:
                front_leg, back_leg = left_leg, right_leg
            else:
                front_leg, back_leg = right_leg, left_leg
            return self.active_workout.update(
                front_leg["hip"], front_leg["knee"], front_leg["ankle"],
                back_leg["hip"], back_leg["knee"], back_leg["ankle"],
            )
        return MOVE_INTO_VIEW

    # ---- Full-body exercises ----------------------------------------------

    def _run_jumping_jacks(self, landmarks):
        left_arm = self.landmark_manager.get_left_arm(landmarks)
        right_arm = self.landmark_manager.get_right_arm(landmarks)
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)
        if (
            left_arm["visibility"] >= VISIBILITY_THRESHOLD
            and right_arm["visibility"] >= VISIBILITY_THRESHOLD
            and left_leg["visibility"] >= VISIBILITY_THRESHOLD
            and right_leg["visibility"] >= VISIBILITY_THRESHOLD
        ):
            return self.active_workout.update(
                left_arm["shoulder"], right_arm["shoulder"],
                left_leg["hip"], right_leg["hip"],
                left_arm["wrist"], right_arm["wrist"],
                left_leg["ankle"], right_leg["ankle"],
            )
        return MOVE_INTO_VIEW

    def _run_burpees(self, landmarks):
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)
        arm = self.landmark_manager.get_best_arm(landmarks)
        if left_leg["visibility"] >= VISIBILITY_THRESHOLD and right_leg["visibility"] >= VISIBILITY_THRESHOLD and arm["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(
                arm["shoulder"], left_leg["hip"], left_leg["knee"], left_leg["ankle"],
                arm["shoulder"], right_leg["hip"], right_leg["knee"], right_leg["ankle"],
            )
        return MOVE_INTO_VIEW

    def _run_crossover_toe_touch(self, landmarks):
        left_arm = self.landmark_manager.get_left_arm(landmarks)
        right_arm = self.landmark_manager.get_right_arm(landmarks)
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)
        if (
            left_arm["visibility"] >= VISIBILITY_THRESHOLD
            and right_arm["visibility"] >= VISIBILITY_THRESHOLD
            and left_leg["visibility"] >= VISIBILITY_THRESHOLD
            and right_leg["visibility"] >= VISIBILITY_THRESHOLD
        ):
            return self.active_workout.update(
                left_arm["shoulder"], right_arm["shoulder"],
                left_leg["hip"], right_leg["hip"],
                left_leg["knee"], right_leg["knee"],
                left_leg["ankle"], right_leg["ankle"],
                left_arm["wrist"], right_arm["wrist"],
            )
        return MOVE_INTO_VIEW