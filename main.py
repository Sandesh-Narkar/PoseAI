"""
main.py
-------
PoseAI - Real-Time AI Fitness Trainer

Entry point that wires together the camera, pose detector, landmark
pipeline, workout logic and on-screen rendering into a single
real-time loop.

Optimized processing pipeline (executed once per frame, in this exact
order, so every stage always operates on data produced by the stage
before it - never a stale or partially-updated frame):

    Camera
      -> Pose Detection
      -> Landmark Extraction
      -> Landmark Validation
      -> Landmark Smoothing
      -> Workout Processing (angle calculation + feedback happens
         inside each workout's update())
      -> Skeleton Drawing
      -> UI Rendering (full desktop dashboard built by UILayout, which
         composes the camera feed, exercise guide, stats and feedback
         panels into a single window using core/exercise_data.py for
         all exercise reference info)
      -> FPS Calculation
      -> Display Frame

Session flow on top of the above pipeline:
    * Each exercise has a goal-rep count and a number of sets
      (core/exercise_data.py). When the active workout's rep count
      reaches the goal, the app pauses and shows a "Set Complete"
      screen (SPACE resumes onto the next set).
    * Once all sets for an exercise are done, an "Exercise Completed"
      screen is shown (ENTER advances to the next exercise).
    * When the user quits (Q), a professional "Session Summary
      Dashboard" is shown before the application actually closes.
      From that dashboard:
        - ENTER returns to exercise selection (menu / first exercise)
          without closing the application.
        - ESC exits PoseAI completely.
Workout algorithms, MediaPipe detection, and all keyboard shortcuts
for selecting exercises are completely unchanged.

Dashboard integration:
    * Whenever workout data meaningfully changes (rep, set, exercise,
      stage, a significant angle shift, feedback, or camera status),
      the latest snapshot is POSTed to the Flask backend's
      /api/update endpoint. This is fire-and-forget: any network
      issue is caught, logged, and ignored - it never interrupts
      pose detection or the workout loop.
"""

import time
from datetime import datetime
import cv2
import mediapipe as mp
import requests

from core.camera import Camera
from core.pose_detector import PoseDetector
from core.landmark_manager import LandmarkManager
from core.landmark_smoother import LandmarkSmoother
from core.drawing import PoseDrawer
from core.ui_layout import UILayout
from core.exercise_data import get_exercise_info

from workouts.bicep import BicepWorkout
from workouts.pushup import PushupWorkout
from workouts.squat import SquatWorkout
from workouts.triceps_pushdown import TricepsPushdownWorkout
from workouts.lunges import LungesWorkout
from workouts.jumping_jacks import JumpingJacksWorkout
from workouts.shoulder_press import ShoulderPressWorkout
from workouts.burpees import BurpeesWorkout
from workouts.warrior2 import Warrior2Workout
from workouts.goblet_squat import GobletSquatWorkout
from workouts.crossover_toe_touch import CrossoverToeTouchWorkout


VISIBILITY_THRESHOLD = 0.5

# Expected number of MediaPipe Pose landmarks per detected body. Used
# to validate a landmark frame before it is trusted for smoothing or
# workout processing - protects against partial/corrupt detections.
EXPECTED_LANDMARK_COUNT = 33

# Key codes used by the session-flow overlays (in addition to the
# regular exercise-selection shortcuts, which are unchanged).
KEY_SPACE = 32
KEY_ENTER_CODES = (13, 10)
KEY_ESC = 27

# Fixed cycle order used when auto-advancing to "the next exercise"
# after an Exercise Completed screen. Matches the existing shortcut
# keys exactly - no new shortcuts are introduced.
EXERCISE_KEY_ORDER = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "g", "t"]

# ---------------------------------------------------------------------------
# DASHBOARD INTEGRATION CONFIGURATION
# ---------------------------------------------------------------------------
# The Flask backend is expected to already be running independently
# (see app.py). These settings control ONLY how/when main.py talks to
# it - they do not affect any pose detection or workout logic.
DASHBOARD_API_URL = "http://127.0.0.1:5000/api/update"
DASHBOARD_REQUEST_TIMEOUT_SECONDS = 0.5

# Minimum change (in degrees) in the tracked joint angle required
# before an update is considered "significant" enough to send.
# Prevents flooding the backend with a POST on every tiny fluctuation.
ANGLE_CHANGE_THRESHOLD_DEGREES = 2.0

MENU_TEXT = """
========== AI FITNESS TRAINER ==========
 1 - Bicep Curl
 2 - Push-up
 3 - Squat
 4 - Triceps Pushdown
 5 - Lunges
 6 - Jumping Jacks
 7 - Shoulder Press
 8 - Burpees
 9 - Warrior II
 G - Goblet Squat
 T - Crossover Toe Touches
 Q - Quit
=========================================
"""


def send_dashboard_update(data: dict) -> None:
    """
    Send the latest workout snapshot to the Flask dashboard backend
    (POST /api/update).

    This function NEVER raises. Any connection error, timeout, or
    other request failure is caught and swallowed so the real-time
    pose detection / workout loop is never interrupted by a dashboard
    that is slow, unreachable, or simply not running.
    """
    try:
        requests.post(
            DASHBOARD_API_URL,
            json=data,
            timeout=DASHBOARD_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout:
        pass
    except requests.exceptions.ConnectionError:
        pass
    except Exception:
        pass


class WorkoutApp:
    def __init__(self):
        self.camera = Camera()
        self.camera.start()
        self.pose_detector = PoseDetector(model_path="models/pose_landmarker_full.task")
        self.landmark_manager = LandmarkManager()
        self.smoother = LandmarkSmoother()
        self.drawer = PoseDrawer()

        # Composes the full desktop UI (header, camera viewport, guide
        # panel, stats panel, feedback panel, and the full-screen
        # session-flow overlays) into a single frame. Created ONCE
        # before the main loop - never rebuilt per frame.
        self.ui = UILayout()

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

        self.exercise_draw_keys = {
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

        # Dispatch table built ONCE at startup instead of every frame.
        # Rebuilding a dict every iteration of the main loop is wasted
        # allocation/CPU work that adds up at real-time framerates.
        self._dispatch = {
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

        # perf_counter is monotonic and immune to system-clock
        # adjustments (NTP sync, DST, manual changes), unlike
        # time.time(), making FPS timing reliable over long sessions.
        self._prev_time = time.perf_counter()

        # Exponential moving average of FPS so the on-screen readout
        # doesn't jitter wildly frame-to-frame while still reacting
        # quickly to genuine performance changes.
        self._fps_smoothed = 0.0
        self._fps_alpha = 0.15

        # Monotonically increasing millisecond timestamp fed to the
        # VIDEO-mode pose detector. Built from perf_counter rather than
        # a simple frame-count increment so it reflects real elapsed
        # time (more accurate tracking/interpolation inside MediaPipe)
        # while still guaranteeing strict monotonicity.
        self._start_time = time.perf_counter()
        self._last_timestamp_ms = -1

        # ---- Session-flow state (display/bookkeeping only - does not
        #      touch any workout algorithm) --------------------------------
        # "ACTIVE"           - normal live detection + dashboard
        # "SET_COMPLETE"      - waiting for SPACE between sets
        # "WORKOUT_COMPLETE"  - waiting for ENTER before next exercise
        self.app_state = "ACTIVE"

        self.current_set = 1
        self.total_sets = 1
        self._goal_reps = 1

        # Reps/FPS accumulated across all sets of the CURRENT exercise.
        self._exercise_total_reps = 0
        self._exercise_fps_samples = []

        # Number of FULLY completed sets for the CURRENT exercise
        # (display/bookkeeping only for the Session Summary Dashboard).
        self._exercise_completed_sets = 0

        # Reps/FPS accumulated across the WHOLE session (all exercises
        # completed or in progress so far), used for the final summary.
        self._session_total_reps = 0
        self._session_fps_samples = []
        self._session_start_time = time.perf_counter()
        self._completed_exercises = 0

        self._workout_start_time = time.perf_counter()

        self.current_key = "1"
        self.active_workout = self.workouts[self.current_key]
        self._sync_exercise_targets()

        # ---- Dashboard integration state (network/formatting only -
        #      does not touch any workout algorithm). Holds the last
        #      payload actually sent so we can detect meaningful
        #      changes and avoid sending on every single frame.
        self._last_dashboard_payload = {}
        self._last_timer_send_time = 0.0

    # ------------------------------------------------------------------ #
    # TIMING HELPERS
    # ------------------------------------------------------------------ #

    def _next_timestamp_ms(self):
        """
        Compute a strictly increasing millisecond timestamp for the
        pose detector's VIDEO mode. MediaPipe requires timestamps to
        never repeat or go backwards - a plain per-frame counter works
        but drifts from real elapsed time if frames are ever dropped
        or delayed. Using perf_counter keeps timestamps meaningful
        while a fallback guarantees monotonicity regardless.
        """
        elapsed_ms = int((time.perf_counter() - self._start_time) * 1000)
        if elapsed_ms <= self._last_timestamp_ms:
            elapsed_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = elapsed_ms
        return elapsed_ms

    def _compute_fps(self):
        """
        Compute instantaneous FPS from monotonic time deltas, then
        blend it into a smoothed running value so the HUD reads
        stable numbers instead of flickering between frames.
        """
        current_time = time.perf_counter()
        delta = current_time - self._prev_time
        self._prev_time = current_time

        instantaneous_fps = 1.0 / delta if delta > 0 else self._fps_smoothed

        if self._fps_smoothed <= 0.0:
            self._fps_smoothed = instantaneous_fps
        else:
            self._fps_smoothed = (
                self._fps_alpha * instantaneous_fps
                + (1.0 - self._fps_alpha) * self._fps_smoothed
            )

        return self._fps_smoothed

    def _elapsed_workout_time(self):
        """Seconds elapsed since the current exercise was selected."""
        return time.perf_counter() - self._workout_start_time

    def _elapsed_session_time(self):
        """Seconds elapsed since the application started."""
        return time.perf_counter() - self._session_start_time

    @staticmethod
    def _average(values):
        """Simple mean helper that safely handles an empty sequence."""
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _estimate_calories(total_reps, total_time_seconds):
        """
        Rough calorie estimate blending a small per-rep cost with a
        baseline per-minute burn rate for moderate-intensity bodyweight
        training. Intentionally simple - flagged to the user as an
        estimate, not a medical-grade calculation.
        """
        minutes = total_time_seconds / 60.0
        return total_reps * 0.32 + minutes * 4.0

    @staticmethod
    def _average_rep_speed(total_reps, total_time_seconds):
        """
        Average repetition speed expressed as reps-per-minute, for the
        Session Summary Dashboard. Purely a display metric - does not
        touch any workout algorithm.
        """
        if total_reps <= 0 or total_time_seconds <= 0:
            return 0.0
        minutes = total_time_seconds / 60.0
        return total_reps / minutes if minutes > 0 else 0.0

    @staticmethod
    def _completion_percentage(completed_sets, goal_sets):
        """Percentage of the current exercise's target sets completed."""
        if goal_sets <= 0:
            return 0.0
        return min(100.0, (completed_sets / goal_sets) * 100.0)

    @staticmethod
    def _performance_rating(total_reps, average_fps):
        """Simple heuristic rating based on volume completed and tracking quality."""
        if total_reps >= 50 and average_fps >= 20:
            return "Excellent"
        if total_reps >= 20:
            return "Good"
        return "Needs Improvement"

    # ------------------------------------------------------------------ #
    # EXERCISE / SESSION STATE HELPERS
    # ------------------------------------------------------------------ #

    def _sync_exercise_targets(self):
        """
        Refresh the goal-rep count and number of sets for the current
        exercise from core/exercise_data.py. Does not touch any
        workout algorithm - purely session/display bookkeeping.
        """
        info = get_exercise_info(self.current_key)
        self.total_sets = max(1, int(info.get("sets", 1) or 1))
        self._goal_reps = max(1, int(info.get("goal", 1) or 1))

    def _switch_exercise(self, key):
        """
        Switch the active exercise and reset all per-exercise session
        counters. The workout object itself is reset via its existing
        reset() method - no algorithm changes.
        """
        self.current_key = key
        self.active_workout = self.workouts[key]
        self.active_workout.reset()
        self._sync_exercise_targets()

        self.current_set = 1
        self._exercise_total_reps = 0
        self._exercise_fps_samples = []
        self._exercise_completed_sets = 0
        self._workout_start_time = time.perf_counter()
        self.app_state = "ACTIVE"

    def _advance_to_next_set(self):
        """Move from SET_COMPLETE back into ACTIVE for the next set."""
        self.current_set += 1
        self.active_workout.reset()
        self.app_state = "ACTIVE"

    def _advance_to_next_exercise(self):
        """Bank the finished exercise's reps and cycle to the next one."""
        self._session_total_reps += self._exercise_total_reps
        self._session_fps_samples.extend(self._exercise_fps_samples)
        self._completed_exercises += 1

        current_index = EXERCISE_KEY_ORDER.index(self.current_key)
        next_key = EXERCISE_KEY_ORDER[(current_index + 1) % len(EXERCISE_KEY_ORDER)]
        self._switch_exercise(next_key)

    def _return_to_exercise_selection(self):
        """
        Reset the whole session (as if the app had just started) and
        drop back into exercise selection at the menu. Triggered by
        pressing ENTER on the Session Summary Dashboard. Does not
        release the camera or close the window - the app keeps running.
        """
        self._session_total_reps = 0
        self._session_fps_samples = []
        self._session_start_time = time.perf_counter()
        self._completed_exercises = 0

        self._switch_exercise("1")
        print(MENU_TEXT)

    # ------------------------------------------------------------------ #
    # INPUT HANDLING
    # ------------------------------------------------------------------ #

    def _handle_key(self, key_char):
        """Handles the ORIGINAL exercise-selection shortcuts - unchanged behavior."""
        if not key_char:
            return
        key_char = key_char.lower()
        if key_char in self.workouts and key_char != self.current_key:
            # Manually switching exercise banks whatever progress was
            # made on the exercise being left, same as finishing it.
            self._session_total_reps += self._exercise_total_reps
            self._session_fps_samples.extend(self._exercise_fps_samples)
            self._switch_exercise(key_char)

    # ------------------------------------------------------------------ #
    # LANDMARK VALIDATION
    # ------------------------------------------------------------------ #

    @staticmethod
    def _landmarks_valid(landmarks):
        """
        Confirm a landmark frame is safe to hand to the smoother and
        workout logic. Guards against MediaPipe occasionally emitting
        a short/empty list during a temporarily lost detection, which
        would otherwise crash downstream indexing (e.g. get_left_leg
        accessing a fixed landmark index).
        """
        return bool(landmarks) and len(landmarks) >= EXPECTED_LANDMARK_COUNT

    # ------------------------------------------------------------------ #
    # PER-WORKOUT LANDMARK ROUTING
    # ------------------------------------------------------------------ #

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
        if (left_leg["visibility"] >= VISIBILITY_THRESHOLD
                and right_leg["visibility"] >= VISIBILITY_THRESHOLD):
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

        if (left_arm["visibility"] >= VISIBILITY_THRESHOLD
                and right_arm["visibility"] >= VISIBILITY_THRESHOLD
                and left_leg["visibility"] >= VISIBILITY_THRESHOLD
                and right_leg["visibility"] >= VISIBILITY_THRESHOLD):
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

        if (left_arm["visibility"] >= VISIBILITY_THRESHOLD
                and right_arm["visibility"] >= VISIBILITY_THRESHOLD):
            return self.active_workout.update(
                left_arm["shoulder"], left_arm["elbow"], left_arm["wrist"],
                right_arm["shoulder"], right_arm["elbow"], right_arm["wrist"],
            )
        return {"feedback": "Move Into Camera View"}

    def _run_burpees(self, landmarks):
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)
        arm = self.landmark_manager.get_best_arm(landmarks)

        if (left_leg["visibility"] >= VISIBILITY_THRESHOLD
                and right_leg["visibility"] >= VISIBILITY_THRESHOLD
                and arm["visibility"] >= VISIBILITY_THRESHOLD):
            return self.active_workout.update(
                arm["shoulder"], left_leg["hip"], left_leg["knee"], left_leg["ankle"],
                arm["shoulder"], right_leg["hip"], right_leg["knee"], right_leg["ankle"],
            )
        return {"feedback": "Move Into Camera View"}

    def _run_warrior2(self, landmarks):
        left_leg = self.landmark_manager.get_left_leg(landmarks)
        right_leg = self.landmark_manager.get_right_leg(landmarks)

        if (left_leg["visibility"] >= VISIBILITY_THRESHOLD
                and right_leg["visibility"] >= VISIBILITY_THRESHOLD):
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

        if (left_leg["visibility"] >= VISIBILITY_THRESHOLD
                and right_leg["visibility"] >= VISIBILITY_THRESHOLD):
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

        if (left_arm["visibility"] >= VISIBILITY_THRESHOLD
                and right_arm["visibility"] >= VISIBILITY_THRESHOLD
                and left_leg["visibility"] >= VISIBILITY_THRESHOLD
                and right_leg["visibility"] >= VISIBILITY_THRESHOLD):
            return self.active_workout.update(
                left_arm["shoulder"], right_arm["shoulder"],
                left_leg["hip"], right_leg["hip"],
                left_leg["knee"], right_leg["knee"],
                left_leg["ankle"], right_leg["ankle"],
                left_arm["wrist"], right_arm["wrist"],
            )
        return {"feedback": "Move Into Camera View"}

    def _run_active_workout(self, landmarks):
        handler = self._dispatch.get(self.current_key)
        if handler is None:
            return None
        return handler(landmarks)

    # ------------------------------------------------------------------ #
    # DASHBOARD INTEGRATION
    # ------------------------------------------------------------------ #

    def _build_dashboard_payload(self, result, reps, camera_connected):
        """
        Assemble the JSON payload describing the current workout state
        for the Flask dashboard backend. Purely a formatting step -
        reads values that have already been computed elsewhere in the
        loop, never recalculates any workout logic (reps, stage, angle,
        feedback all come straight from `result`, which is produced by
        the unchanged workout `update()` methods).
        """
        result = result or {}

        minutes, seconds = divmod(int(self._elapsed_workout_time()), 60)
        workout_time_str = f"{minutes:02d}:{seconds:02d}"

        session_reps_so_far = self._session_total_reps + self._exercise_total_reps + reps
        session_time_seconds = self._elapsed_session_time()
        estimated_calories = round(
            self._estimate_calories(session_reps_so_far, session_time_seconds), 2
        )
        feedback_message = result.get("feedback", "") or "Waiting for Camera..."

        return {
            "exercise": self.active_workout.name,
            "currentRep": reps,
            "goalRep": self._goal_reps,
            "currentSet": self.current_set,
            "goalSet": self.total_sets,
            "stage": result.get("stage", "Waiting..."),
            "angle": int(result.get("angle")) if result.get("angle") is not None else 0,
            "calories": estimated_calories,
            "workoutTime": workout_time_str,
            "feedback": feedback_message,
            "xp": session_reps_so_far,
            "streak": 0,
            "goal": self._goal_reps,
            "cameraStatus": "online" if camera_connected else "offline",
            "statistics": {
                "totalReps": session_reps_so_far,
                "workoutTime": workout_time_str,
                "calories": estimated_calories,
                "xp": session_reps_so_far,
                "exercisesCompleted": self._completed_exercises,
            },
            "coach": {
                "message": feedback_message,
                "type": "success" if feedback_message and "good" in feedback_message.lower() else "info",
            },
            "summary": {
                "exercise": self.active_workout.name,
                "sets": self.current_set,
                "reps": reps,
                "workoutTime": workout_time_str,
                "calories": estimated_calories,
                "xp": session_reps_so_far,
                "streak": 0,
            },
        }

    def _payload_has_significant_change(self, new_payload):
        """
        Compare a freshly built payload against the last one actually
        sent to the dashboard, returning True only if something worth
        reporting changed: rep, set, exercise, stage, feedback, camera
        status, or a significant (>= ANGLE_CHANGE_THRESHOLD_DEGREES)
        shift in the tracked angle. Prevents flooding the backend with
        a POST on every single processed frame.
        """
        last = self._last_dashboard_payload
        if not last:
            return True

        if last.get("exercise") != new_payload.get("exercise"):
            return True

        if last.get("currentRep") != new_payload.get("currentRep"):
            return True

        if last.get("currentSet") != new_payload.get("currentSet"):
            return True

        if last.get("goalSet") != new_payload.get("goalSet"):
            return True

        if last.get("goalRep") != new_payload.get("goalRep"):
            return True

        if last.get("stage") != new_payload.get("stage"):
            return True

        if last.get("feedback") != new_payload.get("feedback"):
            return True

        if last.get("cameraStatus") != new_payload.get("cameraStatus"):
            return True

        if last.get("xp") != new_payload.get("xp"):
            return True

        if last.get("streak") != new_payload.get("streak"):
            return True

        if last.get("calories") != new_payload.get("calories"):
            return True

        current_time = time.perf_counter()
        if current_time - self._last_timer_send_time >= 1.0:
            self._last_timer_send_time = current_time
            return True

        last_angle = last.get("angle")
        new_angle = new_payload.get("angle")

        if last_angle is None or new_angle is None:
            return last_angle != new_angle

        try:
            return abs(float(new_angle) - float(last_angle)) >= ANGLE_CHANGE_THRESHOLD_DEGREES
        except (TypeError, ValueError):
            return True

    def _maybe_update_dashboard(self, result, reps, camera_connected=True):
        """
        Build the current dashboard payload and send it to the Flask
        backend ONLY if it differs meaningfully from the last payload
        sent. Wrapped in its own try/except (in addition to the
        never-raising send_dashboard_update) so that even a failure
        while building the payload can never interrupt the workout
        loop or pose detection.
        """
        try:
            payload = self._build_dashboard_payload(result, reps, camera_connected)
            if self._payload_has_significant_change(payload):
                send_dashboard_update(payload)
                self._last_dashboard_payload = payload
        except Exception:
            print("POST Failed")

    # ------------------------------------------------------------------ #
    # SESSION EXIT / SESSION SUMMARY DASHBOARD
    # ------------------------------------------------------------------ #

    def _show_session_summary(self, in_progress_reps=0):
        """
        Build and display the professional Session Summary Dashboard,
        then wait for the user to choose what happens next:

            ENTER -> return to exercise selection (app keeps running)
            ESC   -> exit PoseAI completely

        Returns the string "restart" or "exit" so run() can react.
        Camera/window teardown only happens on "exit".
        """
        completed_sets = self._exercise_completed_sets
        goal_sets = self.total_sets

        total_reps = self._session_total_reps + self._exercise_total_reps + in_progress_reps
        total_time = self._elapsed_session_time()
        average_fps = self._average(self._session_fps_samples + self._exercise_fps_samples)
        calories = self._estimate_calories(total_reps, total_time)
        avg_rep_speed = self._average_rep_speed(total_reps, total_time)
        completion_pct = self._completion_percentage(completed_sets, goal_sets)
        rating = self._performance_rating(total_reps, average_fps)
        timestamp_str = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

        summary_frame = self.ui.render_session_summary(
            workout_name=self.active_workout.name,
            completed_sets=completed_sets,
            goal_sets=goal_sets,
            total_time=total_time,
            total_reps=total_reps,
            average_fps=average_fps,
            calories=calories,
            avg_rep_speed=avg_rep_speed,
            completion_pct=completion_pct,
            rating=rating,
            timestamp_str=timestamp_str,
        )

        action = None
        while True:
            cv2.imshow("AI Fitness Trainer", summary_frame)
            key = cv2.waitKey(1) & 0xFF
            if key == KEY_ESC:
                action = "exit"
                break
            if key in KEY_ENTER_CODES:
                action = "restart"
                break

        if action == "exit":
            self.camera.release()
            cv2.destroyAllWindows()

        return action

    # ------------------------------------------------------------------ #
    # MAIN LOOP
    # ------------------------------------------------------------------ #

    def run(self):
        print(MENU_TEXT)

        while True:
            # ---- 1. CAMERA -------------------------------------------------
            frame = self.camera.read_frame()
            if frame is None:
                self._maybe_update_dashboard(None, 0, camera_connected=False)
                break

            reps = 0

            if self.app_state == "ACTIVE":
                # ---- 2. POSE DETECTION ------------------------------------------
                detection_result = None
                try:
                    mp_image = mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                    )
                    timestamp_ms = self._next_timestamp_ms()
                    detection_result = self.pose_detector.detect(mp_image, timestamp_ms)
                except Exception:
                    detection_result = None

                # ---- 3. LANDMARK EXTRACTION + 4. VALIDATION ---------------------
                landmarks = None
                has_valid_pose = bool(detection_result and detection_result.pose_landmarks)

                if has_valid_pose:
                    try:
                        raw_landmarks = self.landmark_manager.get_landmarks(detection_result)
                    except Exception:
                        raw_landmarks = None

                    if self._landmarks_valid(raw_landmarks):
                        # ---- 5. LANDMARK SMOOTHING ------------------------------
                        landmarks = self.smoother.smooth(raw_landmarks)
                    else:
                        has_valid_pose = False

                # ---- 6. WORKOUT PROCESSING (angles + feedback happen inside
                #         each workout's update()) -------------------------------
                result = None
                if has_valid_pose and landmarks is not None:
                    try:
                        result = self._run_active_workout(landmarks)
                    except Exception:
                        result = {"feedback": "Move Into Camera View"}
                else:
                    self.smoother.reset()
                    result = {"feedback": "Move Into Camera View"}

                # ---- 9. SKELETON DRAWING -----------------------------------------
                fps = self._compute_fps()
                frame = self.drawer.draw(
                    frame,
                    detection_result,
                    exercise_name=self.exercise_draw_keys.get(self.current_key),
                    workout_data=result,
                    fps=fps,
                    show_angles=True,
                    show_confidence=True,
                )

                self._exercise_fps_samples.append(fps)
                reps = int((result or {}).get("reps", 0) or 0)

                # ---- DASHBOARD INTEGRATION: send only on meaningful change ------
                self._maybe_update_dashboard(result, reps, camera_connected=True)

                # ---- 10. UI RENDERING ---------------------------------------------
                combined_frame = self.ui.render(
                    camera_frame=frame,
                    workout_name=self.active_workout.name,
                    workout_data=result or {},
                    fps=fps,
                    elapsed_time=self._elapsed_workout_time(),
                    current_set=self.current_set,
                    total_sets=self.total_sets,
                )

                # ---- SESSION FLOW: check for set / exercise completion -----------
                if reps >= self._goal_reps:
                    self._exercise_total_reps += reps
                    self._exercise_completed_sets += 1
                    if self.current_set < self.total_sets:
                        self.app_state = "SET_COMPLETE"
                    else:
                        self.app_state = "WORKOUT_COMPLETE"

            elif self.app_state == "SET_COMPLETE":
                combined_frame = self.ui.render_set_complete(
                    workout_name=self.active_workout.name,
                    current_set=self.current_set,
                    total_sets=self.total_sets,
                )

            else:  # "WORKOUT_COMPLETE"
                combined_frame = self.ui.render_workout_complete(
                    workout_name=self.active_workout.name,
                    total_reps=self._exercise_total_reps,
                    workout_time=self._elapsed_workout_time(),
                    average_fps=self._average(self._exercise_fps_samples),
                )

            # ---- 11. DISPLAY FRAME ------------------------------------------
            cv2.imshow("AI Fitness Trainer", combined_frame)

            key = cv2.waitKey(1) & 0xFF
            key_char = chr(key) if 32 <= key < 127 else ""

            if self.app_state == "ACTIVE":
                if key_char.lower() == "q":
                    action = self._show_session_summary(in_progress_reps=reps)
                    if action == "exit":
                        return
                    self._return_to_exercise_selection()
                    continue
                self._handle_key(key_char)

            elif self.app_state == "SET_COMPLETE":
                if key_char.lower() == "q":
                    action = self._show_session_summary()
                    if action == "exit":
                        return
                    self._return_to_exercise_selection()
                    continue
                if key == KEY_SPACE:
                    self._advance_to_next_set()

            else:  # "WORKOUT_COMPLETE"
                if key_char.lower() == "q":
                    action = self._show_session_summary()
                    if action == "exit":
                        return
                    self._return_to_exercise_selection()
                    continue
                if key in KEY_ENTER_CODES:
                    self._advance_to_next_exercise()

        self.camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    app = WorkoutApp()
    app.run()