"""
WebWorkoutEngine
----------------
A lightweight version of the desktop workout loop designed for the Flask
web dashboard. It reuses the existing MediaPipe pose detector, landmark
manager, smoother, and workout classes without opening an OpenCV window.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

import cv2
import numpy as np
import mediapipe as mp

from core.exercise_data import get_exercise_info
from core.landmark_manager import LandmarkManager
from core.landmark_smoother import LandmarkSmoother
from core.pose_detector import PoseDetector
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

logger = logging.getLogger("poseai.web_engine")

VISIBILITY_THRESHOLD = 0.5
EXPECTED_LANDMARK_COUNT = 33


class WebWorkoutEngine:
    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self.pose_detector = PoseDetector(model_path="models/pose_landmarker_full.task")
        self.landmark_manager = LandmarkManager()
        self.smoother = LandmarkSmoother()

        self.workouts = {
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
        self.current_key = "1"
        self.active_workout = self.workouts[self.current_key]
        self._session_start_time = time.perf_counter()
        self._workout_start_time = time.perf_counter()
        self._exercise_total_reps = 0
        self._session_total_reps = 0
        self._exercise_fps_samples: list[float] = []
        self._session_fps_samples: list[float] = []
        self._last_timestamp_ms = -1
        self._last_payload: dict[str, Any] = {}
        self._last_timer_send_time = 0.0
        self._active = False
        self._paused = False
        self._completed = False
        self._current_set = 1
        self.total_sets = 3
        self._goal_reps = 15
        self._sync_exercise_targets()

    def _sync_exercise_targets(self) -> None:
        info = get_exercise_info(self.current_key)
        self.total_sets = max(1, int(info.get("sets", 1) or 1))
        self._goal_reps = max(1, int(info.get("goal", 1) or 1))

    @staticmethod
    def _estimate_calories(total_reps: int, total_time_seconds: float) -> float:
        minutes = total_time_seconds / 60.0
        return round(total_reps * 0.32 + minutes * 4.0, 2)

    @staticmethod
    def _elapsed_time_seconds(start_time: float) -> int:
        return int(max(0.0, time.perf_counter() - start_time))

    @staticmethod
    def _format_timer(seconds: int) -> str:
        minutes, remainder = divmod(seconds, 60)
        return f"{minutes:02d}:{remainder:02d}"

    @staticmethod
    def _landmarks_valid(landmarks) -> bool:
        return bool(landmarks) and len(landmarks) >= EXPECTED_LANDMARK_COUNT

    def set_exercise(self, exercise: str | None) -> dict[str, Any]:
        key = exercise or self.current_key
        if key not in self.workouts:
            key = self.current_key
        self.current_key = key
        self.active_workout = self.workouts[self.current_key]
        self.active_workout.reset()
        self._sync_exercise_targets()
        self._workout_start_time = time.perf_counter()
        self._current_set = 1
        self._exercise_total_reps = 0
        self._exercise_fps_samples = []
        self._active = True
        self._paused = False
        self._completed = False

        if self.debug:
            logger.info("[PoseAI] Exercise selected: %s", self.active_workout.name)
        return self.get_status()

    def start(self, exercise: str | None = None) -> dict[str, Any]:
        self._active = True
        self._paused = False
        self._completed = False
        self._workout_start_time = time.perf_counter()
        return self.set_exercise(exercise)

    def pause(self) -> dict[str, Any]:
        self._paused = True
        return self.get_status()

    def resume(self) -> dict[str, Any]:
        self._paused = False
        self._active = True
        return self.get_status()

    def finish(self) -> dict[str, Any]:
        self._active = False
        self._paused = False
        self._completed = True
        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        elapsed_seconds = self._elapsed_time_seconds(self._workout_start_time)
        return {
            "exercise": self.active_workout.name,
            "currentRep": getattr(self.active_workout, "reps", 0),
            "goalRep": self._goal_reps,
            "currentSet": self._current_set,
            "goalSet": self.total_sets,
            "stage": getattr(self.active_workout, "stage", "Waiting..."),
            "angle": 0,
            "calories": self._estimate_calories(self._session_total_reps + self._exercise_total_reps, self._elapsed_time_seconds(self._session_start_time)),
            "workoutTime": self._format_timer(elapsed_seconds),
            "feedback": getattr(self.active_workout, "feedback", "Waiting for Camera..."),
            "xp": self._session_total_reps + self._exercise_total_reps,
            "streak": 0,
            "goal": self._goal_reps,
            "cameraStatus": "paused" if self._paused else "tracking" if self._active else "idle",
            "sessionStatus": "active" if self._active and not self._paused else "paused" if self._paused else "completed",
            "trackingStatus": "tracking" if self._active and not self._paused else "paused" if self._paused else "idle",
            "statistics": {
                "totalReps": self._session_total_reps + self._exercise_total_reps,
                "workoutTime": self._format_timer(elapsed_seconds),
                "calories": self._estimate_calories(self._session_total_reps + self._exercise_total_reps, self._elapsed_time_seconds(self._session_start_time)),
                "xp": self._session_total_reps + self._exercise_total_reps,
                "exercisesCompleted": 0,
            },
            "coach": {
                "message": getattr(self.active_workout, "feedback", "Waiting for Camera..."),
                "type": "success" if getattr(self.active_workout, "feedback", "") and "good" in str(getattr(self.active_workout, "feedback", "")).lower() else "info",
            },
            "summary": {
                "exercise": self.active_workout.name,
                "sets": self._current_set,
                "reps": getattr(self.active_workout, "reps", 0),
                "workoutTime": self._format_timer(elapsed_seconds),
                "calories": self._estimate_calories(self._session_total_reps + self._exercise_total_reps, self._elapsed_time_seconds(self._session_start_time)),
                "xp": self._session_total_reps + self._exercise_total_reps,
                "streak": 0,
            },
        }

    def _next_timestamp_ms(self) -> int:
        elapsed_ms = int((time.perf_counter() - self._session_start_time) * 1000)
        if elapsed_ms <= self._last_timestamp_ms:
            elapsed_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = elapsed_ms
        return elapsed_ms

    def _run_active_workout(self, landmarks):
        handler = {
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
        }.get(self.current_key)
        if handler is None:
            return {"feedback": "Move Into Camera View"}
        return handler(landmarks)

    def _run_bicep_curl(self, landmarks):
        arm = self.landmark_manager.get_best_arm(landmarks)
        if arm["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(arm["shoulder"], arm["elbow"], arm["wrist"])
        return {"feedback": "Move Into Camera View"}

    def _run_pushup(self, landmarks):
        arm = self.landmark_manager.get_best_arm(landmarks)
        if arm["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(arm["shoulder"], arm["elbow"], arm["wrist"])
        return {"feedback": "Move Into Camera View"}

    def _run_squat(self, landmarks):
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)
        if left_leg["visibility"] >= VISIBILITY_THRESHOLD and right_leg["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(
                left_leg["hip"], left_leg["knee"], left_leg["ankle"],
                right_leg["hip"], right_leg["knee"], right_leg["ankle"],
            )
        return {"feedback": "Move Into Camera View"}

    def _run_triceps_pushdown(self, landmarks):
        arm = self.landmark_manager.get_best_arm(landmarks)
        if arm["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(arm["shoulder"], arm["elbow"], arm["wrist"])
        return {"feedback": "Move Into Camera View"}

    def _run_lunges(self, landmarks):
        leg = self.landmark_manager.get_best_leg(landmarks)
        if leg["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(leg["hip"], leg["knee"], leg["ankle"])
        return {"feedback": "Move Into Camera View"}

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
        return {"feedback": "Move Into Camera View"}

    def _run_shoulder_press(self, landmarks):
        left_arm = self.landmark_manager.get_left_arm(landmarks)
        right_arm = self.landmark_manager.get_right_arm(landmarks)
        if left_arm["visibility"] >= VISIBILITY_THRESHOLD and right_arm["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(
                left_arm["shoulder"], left_arm["elbow"], left_arm["wrist"],
                right_arm["shoulder"], right_arm["elbow"], right_arm["wrist"],
            )
        return {"feedback": "Move Into Camera View"}

    def _run_burpees(self, landmarks):
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)
        arm = self.landmark_manager.get_best_arm(landmarks)
        if left_leg["visibility"] >= VISIBILITY_THRESHOLD and right_leg["visibility"] >= VISIBILITY_THRESHOLD and arm["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(
                arm["shoulder"], left_leg["hip"], left_leg["knee"], left_leg["ankle"],
                arm["shoulder"], right_leg["hip"], right_leg["knee"], right_leg["ankle"],
            )
        return {"feedback": "Move Into Camera View"}

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
        return {"feedback": "Move Into Camera View"}

    def _run_goblet_squat(self, landmarks):
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)
        if left_leg["visibility"] >= VISIBILITY_THRESHOLD and right_leg["visibility"] >= VISIBILITY_THRESHOLD:
            return self.active_workout.update(
                left_leg["hip"], left_leg["knee"], left_leg["ankle"],
                right_leg["hip"], right_leg["knee"], right_leg["ankle"],
            )
        return {"feedback": "Move Into Camera View"}

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
        return {"feedback": "Move Into Camera View"}

    def process_frame(self, encoded_frame: str | None, exercise: str | None = None) -> dict[str, Any]:
        if not encoded_frame:
            return {"feedback": "Camera frame missing"}

        if self.debug:
            logger.info("[PoseAI] Camera frame received")

        if exercise:
            self.set_exercise(exercise)

        if self._paused:
            return self.get_status()

        try:
            image_bytes = base64.b64decode(encoded_frame.split(",", 1)[-1])
            frame_array = np.frombuffer(image_bytes, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("Unable to decode frame")
        except Exception as exc:
            logger.warning("[PoseAI] Frame decode failed: %s", exc)
            return self.get_status()

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            timestamp_ms = self._next_timestamp_ms()
            detection_result = self.pose_detector.detect(mp_image, timestamp_ms)
        except Exception as exc:
            logger.warning("[PoseAI] Pose detection failed: %s", exc)
            return self.get_status()

        landmarks = None
        if detection_result and getattr(detection_result, "pose_landmarks", None):
            try:
                raw_landmarks = self.landmark_manager.get_landmarks(detection_result)
            except Exception:
                raw_landmarks = None
            if self._landmarks_valid(raw_landmarks):
                landmarks = self.smoother.smooth(raw_landmarks)

        if landmarks is not None:
            try:
                result = self._run_active_workout(landmarks)
            except Exception as exc:
                logger.warning("[PoseAI] Workout update failed: %s", exc)
                result = {"feedback": "Move Into Camera View"}
        else:
            self.smoother.reset()
            result = {"feedback": "Move Into Camera View"}

        reps = int((result or {}).get("reps", 0) or 0)
        if reps > 0:
            self._exercise_total_reps = max(self._exercise_total_reps, reps)

        payload = self._build_payload(result, reps)
        self._last_payload = payload
        if self.debug:
            logger.info("[PoseAI] Exercise: %s | Angle: %s | Stage: %s | Rep: %s", payload.get("exercise"), payload.get("angle"), payload.get("stage"), payload.get("currentRep"))
        return payload

    def _build_payload(self, result: dict[str, Any], reps: int) -> dict[str, Any]:
        workout_time = self._format_timer(self._elapsed_time_seconds(self._workout_start_time))
        session_time_seconds = self._elapsed_time_seconds(self._session_start_time)
        estimated_calories = self._estimate_calories(self._session_total_reps + self._exercise_total_reps + reps, session_time_seconds)
        feedback_message = (result or {}).get("feedback") or "Waiting for Camera..."
        angle_value = (result or {}).get("angle")
        if angle_value is None:
            angle_value = 0

        return {
            "exercise": self.active_workout.name,
            "currentRep": reps,
            "goalRep": self._goal_reps,
            "currentSet": self._current_set,
            "goalSet": self.total_sets,
            "stage": (result or {}).get("stage", "Waiting..."),
            "angle": int(angle_value) if isinstance(angle_value, (int, float)) else 0,
            "calories": estimated_calories,
            "workoutTime": workout_time,
            "feedback": feedback_message,
            "xp": self._session_total_reps + self._exercise_total_reps + reps,
            "streak": 0,
            "goal": self._goal_reps,
            "cameraStatus": "tracking" if not self._paused and self._active else "paused" if self._paused else "idle",
            "sessionStatus": "active" if self._active and not self._paused else "paused" if self._paused else "completed",
            "trackingStatus": "tracking" if self._active and not self._paused else "paused" if self._paused else "idle",
            "statistics": {
                "totalReps": self._session_total_reps + self._exercise_total_reps + reps,
                "workoutTime": workout_time,
                "calories": estimated_calories,
                "xp": self._session_total_reps + self._exercise_total_reps + reps,
                "exercisesCompleted": 0,
            },
            "coach": {
                "message": feedback_message,
                "type": "success" if feedback_message and "good" in feedback_message.lower() else "info",
            },
            "summary": {
                "exercise": self.active_workout.name,
                "sets": self._current_set,
                "reps": self._session_total_reps + self._exercise_total_reps + reps,
                "workoutTime": workout_time,
                "calories": estimated_calories,
                "xp": self._session_total_reps + self._exercise_total_reps + reps,
                "streak": 0,
            },
        }
