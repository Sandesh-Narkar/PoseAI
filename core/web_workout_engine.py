"""
WebWorkoutEngine
----------------
A lightweight version of the desktop workout loop designed for the Flask
web dashboard. It reuses the existing MediaPipe pose detector, landmark
smoother, and the SAME per-exercise routing engine as the desktop app
(core/exercise_router.py - also used by main.py), without opening an
OpenCV window. "One engine, two input sources":
    - desktop: main.py  -> OpenCV camera -> ExerciseRouter -> workouts/*
    - web:     app.py   -> browser frames -> ExerciseRouter -> workouts/*
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
from core.exercise_router import ExerciseRouter, normalize_exercise_key
from core.landmark_smoother import LandmarkSmoother
from core.pose_detector import PoseDetector

logger = logging.getLogger("poseai.web_engine")

EXPECTED_LANDMARK_COUNT = 33


class WebWorkoutEngine:
    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self.pose_detector = PoseDetector(model_path="models/pose_landmarker_full.task")
        # Shared, camera-independent routing engine - the SAME exercise
        # logic the desktop app (main.py) uses. Keeps the web and desktop
        # paths on a single implementation ("one engine, two input sources").
        self.router = ExerciseRouter()
        self.landmark_manager = self.router.landmark_manager
        self.smoother = LandmarkSmoother()

        self.workouts = self.router.workouts
        self.current_key = "1"
        self.active_workout = self.router.active_workout
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
        self._set_complete_notified = False
        self._prev_reps = 0
        self._rep_history: list[dict[str, Any]] = []
        self._current_rep_angles: list[float] = []
        self._current_rep_forms: list[float] = []
        self._last_rep_finish_time = time.perf_counter()
        self._sets_data: list[dict[str, Any]] = []
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
        # Accept short keys ("1"), slugs ("bicep_curl") and display names
        # ("Bicep Curl") so Exercises-page links always resolve to the
        # same engine. Unknown values keep the previous selection.
        canonical = normalize_exercise_key(exercise) or self.current_key
        key = canonical
        if not self.router.set_exercise(key):
            key = self.current_key
            self.router.set_exercise(key)
        self.current_key = self.router.current_key
        self.active_workout = self.router.active_workout
        self.active_workout.reset()
        self._sync_exercise_targets()
        self._workout_start_time = time.perf_counter()
        self._current_set = 1
        self._exercise_total_reps = 0
        self._prev_reps = 0
        self._rep_history = []
        self._current_rep_angles = []
        self._current_rep_forms = []
        self._last_rep_finish_time = time.perf_counter()
        self._sets_data = []
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

    def advance_to_next_set(self) -> dict[str, Any]:
        """
        Advance to the next set after a set completion.
        Increments the current set counter and records set telemetry.
        """
        if self._current_set <= self.total_sets:
            completed_set_reps = getattr(self.active_workout, "reps", 0)
            set_reps_list = [r for r in self._rep_history if r.get("set") == self._current_set]
            avg_acc = round(float(np.mean([r["form_accuracy"] for r in set_reps_list])), 1) if set_reps_list else 88.0
            angles = [r["angle"] for r in set_reps_list if r.get("angle") is not None]
            avg_ang = round(float(np.mean(angles)), 1) if angles else 90.0
            min_ang = min(angles) if angles else 45
            max_ang = max(angles) if angles else 160
            tempos = [r["tempo"] for r in set_reps_list if r.get("tempo") is not None]
            avg_tempo = round(float(np.mean(tempos)), 1) if tempos else 1.8
            status = "Completed" if completed_set_reps >= self._goal_reps else "Incomplete"
            
            self._sets_data.append({
                "set_number": self._current_set,
                "target_reps": self._goal_reps,
                "completed_reps": completed_set_reps,
                "accuracy": avg_acc,
                "average_angle": avg_ang,
                "min_angle": min_ang,
                "max_angle": max_ang,
                "average_tempo": avg_tempo,
                "status": status,
            })

            if self._current_set < self.total_sets:
                self._exercise_total_reps += completed_set_reps
                self._current_set += 1
                self._prev_reps = 0
                self._set_complete_notified = False
                self.active_workout.reset()
                self._exercise_fps_samples = []
                if self.debug:
                    logger.info("[WORKOUT] Advanced to set %d/%d (exercise total: %d reps)",
                               self._current_set, self.total_sets, self._exercise_total_reps)
        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        elapsed_seconds = self._elapsed_time_seconds(self._workout_start_time)
        return {
            "exercise": self.active_workout.name,
            "exerciseKey": self.current_key,
            "currentRep": getattr(self.active_workout, "reps", 0),
            "goalRep": self._goal_reps,
            "currentSet": self._current_set,
            "goalSet": self.total_sets,
            "stage": getattr(self.active_workout, "stage", "Waiting...") or "Waiting...",
            "angle": None,
            "form_accuracy": None,
            "pose_detected": False,
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
        # Single shared implementation (ExerciseRouter) - identical logic
        # to the desktop engine in main.py.
        result = self.router.run(landmarks)
        if result is None:
            return {"feedback": "Move Into Camera View"}
        return result

    def process_frame(self, encoded_frame: str | None, exercise: str | None = None) -> dict[str, Any]:
        if not encoded_frame or not isinstance(encoded_frame, str) or not encoded_frame.strip():
            status = self.get_status()
            status.update({
                "feedback": "Camera frame missing",
                "coach": {"message": "Camera frame missing", "type": "info"},
                "pose_detected": False,
            })
            return status

        if self.debug:
            logger.info("[WORKOUT] Frame received | Exercise param: %s | Current: %s", exercise, self.current_key)

        if exercise:
            # Normalize slugs ("bicep_curl") and keys ("1") to the same
            # canonical key so a per-frame `exercise` field can never wipe
            # the rep counter by looking "different" from current_key.
            canonical = normalize_exercise_key(exercise)
            if canonical is not None and canonical != self.current_key:
                # Only switch workouts when the exercise actually changes.
                # set_exercise() resets the active workout (reps, stage,
                # timers), so calling it on every frame would wipe the
                # rep counter that the web UI depends on.
                self.set_exercise(canonical)
            elif canonical is None:
                logger.warning("[WORKOUT] Unknown exercise '%s' on frame; keeping '%s'", exercise, self.current_key)

        if self._paused:
            status = self.get_status()
            status.update({
                "pose_detected": False,
                # Preserve the actual rep count so it survives the paused
                # state and the UI never shows a confusing reset to 0.
                "currentRep": getattr(self.active_workout, "reps", 0),
                "stage": "Paused",
                "angle": None,
                "feedback": "Session paused",
            })
            return status

        try:
            raw = encoded_frame.split(",", 1)[-1] if "," in encoded_frame else encoded_frame
            raw = raw.strip()
            if not raw:
                raise ValueError("Empty frame payload")
            image_bytes = base64.b64decode(raw, validate=False)
            frame_array = np.frombuffer(image_bytes, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("Unable to decode frame (cv2.imdecode returned None)")
            if self.debug:
                height, width = frame.shape[:2]
                logger.info("[WORKOUT] Image decoded: %sx%s", width, height)
        except Exception as exc:
            logger.warning("[WORKOUT] Frame decode failed: %s", exc)
            status = self.get_status()
            status.update({
                "feedback": "Unable to process camera frame",
                "coach": {"message": "Unable to process camera frame", "type": "info"},
                "pose_detected": False,
                "currentRep": 0,
                "stage": "Move Into Camera View",
                "angle": None,
            })
            return status

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            timestamp_ms = self._next_timestamp_ms()
            detection_result = self.pose_detector.detect(mp_image, timestamp_ms)
        except Exception as exc:
            logger.warning("[WORKOUT] Pose detection failed: %s", exc)
            status = self.get_status()
            status.update({
                "pose_detected": False,
                "currentRep": 0,
                "stage": "Move Into Camera View",
                "angle": None,
            })
            return status

        pose_detected = False
        landmarks = None
        if detection_result and getattr(detection_result, "pose_landmarks", None):
            try:
                raw_landmarks = self.landmark_manager.get_landmarks(detection_result)
            except Exception:
                raw_landmarks = None
            if self._landmarks_valid(raw_landmarks):
                pose_detected = True
                landmarks = self.smoother.smooth(raw_landmarks)

        if landmarks is not None:
            try:
                result = self._run_active_workout(landmarks)
            except Exception as exc:
                logger.warning("[WORKOUT] Workout update failed: %s", exc)
                result = {"feedback": "Move Into Camera View"}
        else:
            self.smoother.reset()
            result = {"feedback": "Move Into Camera View"}

        reps = int((result or {}).get("reps", 0) or 0)
        # NOTE: the per-exercise workout object owns the rep counter and
        # persists across frames; nothing here resets it, so reps only ever
        # grow when the exercise engine itself increments them.

        payload = self._build_payload(result, reps, pose_detected=pose_detected)
        self._last_payload = payload
        if self.debug:
            logger.info("[WORKOUT] Exercise: %s | Angle: %s | Stage: %s | Rep: %s | Pose: %s", payload.get("exercise"), payload.get("angle"), payload.get("stage"), payload.get("currentRep"), pose_detected)
        return payload

    @staticmethod
    def _compute_form_accuracy(feedback: str, pose_detected: bool) -> float | None:
        """Map the exercise engine's textual feedback to a deterministic form-accuracy
        score (0–100).  Returns None when pose is not detected so the frontend
        correctly shows '--' instead of a stale or fake number.

        The mapping is derived from what each exercise class actually emits:
          Excellent Rep! / Excellent Form → 95   (perfect execution)
          Good Form                       → 88   (solid)
          Hold Steady / Tracking          → 85   (acceptable, awaiting stability)
          Full ROM coaching messages      → 80   (minor incomplete range)
          Fault messages (form cues)      → 70   (technique needs work)
          Move Into Camera View / no pose → None (no measurement possible)
        """
        if not pose_detected or not feedback:
            return None
        fb = feedback.lower()
        if "move into camera" in fb or "camera frame" in fb or "waiting" in fb:
            return None
        # Tier 1 – perfect rep or excellent hold
        if "excellent rep" in fb or "excellent form" in fb or "perfect" in fb:
            return 95.0
        # Tier 2 – good form detected
        if "good form" in fb or "great form" in fb:
            return 88.0
        # Tier 3 – stable but awaiting confirmation
        if "hold steady" in fb or "tracking" in fb or "good" in fb:
            return 85.0
        # Tier 4 – ROM coaching (incomplete range, not a technique fault)
        if any(t in fb for t in (
            "straighten your arm", "curl higher", "full extension",
            "lower your hips", "go lower", "go deeper", "stand tall",
            "bend your knees", "reach higher", "full rep", "extend fully",
        )):
            return 80.0
        # Tier 5 – active technique fault messages
        if any(t in fb for t in (
            "avoid swinging", "slow down", "control the rep", "keep elbow",
            "keep elbows", "elbow steady", "align your wrist", "keep your back",
            "engage your core", "chest to floor", "too fast", "momentum",
            "flaring", "collapse", "forward", "neutral spine", "hip",
            "shoulder", "poor", "sloppy", "weak", "minimal",
        )):
            return 70.0
        # Default: pose detected, no specific coaching needed
        return 85.0

    def _build_payload(self, result: dict[str, Any], reps: int, pose_detected: bool = True) -> dict[str, Any]:
        workout_time = self._format_timer(self._elapsed_time_seconds(self._workout_start_time))
        session_time_seconds = self._elapsed_time_seconds(self._session_start_time)
        estimated_calories = self._estimate_calories(self._session_total_reps + self._exercise_total_reps + reps, session_time_seconds)
        feedback_message = (result or {}).get("feedback") or "Waiting for Camera..."
        angle_value = (result or {}).get("angle")
        # Honest angle: None when no pose/landmarks (frontend shows "--").
        angle_out = None
        if isinstance(angle_value, (int, float)):
            angle_out = int(angle_value)

        # Deterministic form accuracy derived from the exercise engine's feedback.
        form_accuracy = self._compute_form_accuracy(feedback_message, pose_detected)

        # Collect ongoing frame measurements
        if angle_out is not None:
            self._current_rep_angles.append(angle_out)
        if form_accuracy is not None:
            self._current_rep_forms.append(form_accuracy)

        # Detect completed rep
        if reps > self._prev_reps:
            total_current_rep = self._session_total_reps + self._exercise_total_reps + reps
            now_time = time.perf_counter()
            rep_tempo = round(max(0.5, now_time - self._last_rep_finish_time), 1)
            self._last_rep_finish_time = now_time

            avg_ang = round(float(np.mean(self._current_rep_angles)), 1) if self._current_rep_angles else (angle_out or 90.0)
            avg_acc = round(float(np.mean(self._current_rep_forms)), 1) if self._current_rep_forms else (form_accuracy or 85.0)

            from datetime import datetime as dt
            self._rep_history.append({
                "rep": total_current_rep,
                "set": self._current_set,
                "angle": avg_ang,
                "form_accuracy": avg_acc,
                "tempo": rep_tempo,
                "timestamp": dt.utcnow().isoformat(),
            })
            self._prev_reps = reps
            self._current_rep_angles = []
            self._current_rep_forms = []

        # Determine if current set is completed (one-shot: fires exactly once per set).
        # Once notified, the flag stays True until advance_to_next_set() clears it.
        if reps >= self._goal_reps and self._current_set <= self.total_sets:
            if not self._set_complete_notified:
                set_completed = True
                self._set_complete_notified = True
            else:
                set_completed = False
        else:
            set_completed = False

        return {
            "exercise": self.active_workout.name,
            "exerciseKey": self.current_key,
            "currentRep": reps,
            "goalRep": self._goal_reps,
            "currentSet": self._current_set,
            "goalSet": self.total_sets,
            "set_completed": set_completed,
            "completed_sets": self._current_set if set_completed else max(0, self._current_set - 1),
            "total_reps": self._session_total_reps + self._exercise_total_reps + reps,
            "stage": (result or {}).get("stage") or ("Move Into Camera View" if not pose_detected else "Waiting..."),
            "angle": angle_out,
            "form_accuracy": form_accuracy,
            "pose_detected": pose_detected,
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
                "type": "success" if feedback_message and ("excellent" in feedback_message.lower() or "good" in feedback_message.lower()) else "info",
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

    def _generate_coach_recommendation(self) -> str:
        if not self._rep_history:
            return "Complete your workout sets with steady form to generate personalized AI coaching insights."

        accuracies = [r["form_accuracy"] for r in self._rep_history if r.get("form_accuracy") is not None]
        avg_acc = float(np.mean(accuracies)) if accuracies else 85.0

        tempos = [r["tempo"] for r in self._rep_history if r.get("tempo") is not None]
        avg_tempo = float(np.mean(tempos)) if tempos else 2.0

        if len(accuracies) >= 6:
            first_half = accuracies[:len(accuracies)//2]
            second_half = accuracies[len(accuracies)//2:]
            if np.mean(second_half) < np.mean(first_half) - 5:
                return "Form deterioration was detected in the final repetitions, indicating muscle fatigue. Prioritize controlled breathing and maintain core stability throughout the end of each set."

        if avg_tempo < 1.4:
            return "Your eccentric tempo is slightly fast. Slow down the lowering phase to 2-3 seconds to maximize muscular tension and form control."

        if avg_acc >= 92:
            return "Outstanding form consistency across all reps! Your alignment and movement pacing are optimal. Consider progressing to higher volume or increased resistance."
        elif avg_acc >= 85:
            return "Solid form maintained throughout the session. Keep your joints aligned and focus on complete range of motion at peak contraction."
        else:
            return "Focus on steady joint stabilization. Avoid utilizing momentum to finish the rep, and concentrate on a controlled cadence."

    def get_analytics_summary(self) -> dict[str, Any]:
        form_history = [
            {"rep": r["rep"], "accuracy": r["form_accuracy"]}
            for r in self._rep_history
        ]
        joint_angles = [
            {"rep": r["rep"], "angle": r["angle"]}
            for r in self._rep_history
        ]

        sets = list(self._sets_data)
        current_reps = getattr(self.active_workout, "reps", 0)
        already_has_current_set = any(s.get("set_number") == self._current_set for s in sets)
        if not already_has_current_set and (current_reps > 0 or self._current_set > len(sets)):
            current_set_reps = [r for r in self._rep_history if r.get("set") == self._current_set]
            avg_acc = round(float(np.mean([r["form_accuracy"] for r in current_set_reps])), 1) if current_set_reps else 85.0
            angles = [r["angle"] for r in current_set_reps if r.get("angle") is not None]
            avg_ang = round(float(np.mean(angles)), 1) if angles else 90.0
            min_ang = min(angles) if angles else 45
            max_ang = max(angles) if angles else 160
            tempos = [r["tempo"] for r in current_set_reps if r.get("tempo") is not None]
            avg_tempo = round(float(np.mean(tempos)), 1) if tempos else 1.8
            status = "Completed" if current_reps >= self._goal_reps else ("In Progress" if current_reps > 0 else "Pending")
            sets.append({
                "set_number": self._current_set,
                "target_reps": self._goal_reps,
                "completed_reps": current_reps,
                "accuracy": avg_acc,
                "average_angle": avg_ang,
                "min_angle": min_ang,
                "max_angle": max_ang,
                "average_tempo": avg_tempo,
                "status": status,
            })

        return {
            "rep_history": self._rep_history,
            "form_history": form_history,
            "joint_angles": joint_angles,
            "sets": sets,
            "coach_recommendation": self._generate_coach_recommendation(),
        }
