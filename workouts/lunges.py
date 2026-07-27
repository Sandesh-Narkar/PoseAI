"""
workouts/lunges.py
--------------------
Lunges workout logic.

This module implements a robust, jitter-resistant lunge detector built on
top of the existing BaseWorkout/AngleCalculator architecture.

IMPORTANT ARCHITECTURAL NOTE:
The public update() signature is fixed by the rest of the project as
update(self, hip, knee, ankle) — a single (hip, knee, ankle) landmark set,
already selected as the "best"/leading leg by LandmarkManager.get_best_leg().
Because only one leg's landmarks are passed in per call, this detector
works with the single knee angle it receives (the front/leading leg) and
uses geometric heuristics (stride length, hip drop, hip-over-knee lean,
tracking validity) to approximate the additional posture checks requested
in the spec — front knee, back knee, torso lean, and balance — without
requiring any change to the method signature or upstream classes.
"""

import math

from workouts.base_workout import BaseWorkout
from core.angle_calculator import AngleCalculator


class LungesWorkout(BaseWorkout):

    # --- Angle thresholds (degrees) ---
    STANDING_ANGLE_THRESHOLD = 165   # avg knee angle above this => standing
    LUNGE_ANGLE_MIN = 70             # front knee angle lower bound for a valid lunge
    LUNGE_ANGLE_MAX = 100            # front knee angle upper bound for a valid lunge

    # --- Stability / anti-jitter settings ---
    STABILITY_FRAMES_REQUIRED = 3    # consecutive frames needed before switching stage
    MAX_FRAME_TO_FRAME_JUMP = 35     # degrees; larger jumps are treated as sensor jitter

    # --- Cooldown after a counted rep ---
    REP_COOLDOWN_FRAMES = 15

    # --- Balance / stride heuristics ---
    MIN_STRIDE_RATIO = 0.30          # ankle-to-hip horizontal distance / leg length
    MIN_LEG_LENGTH = 1e-3            # guards against collapsed/invalid landmarks

    # --- Torso lean heuristic ---
    # Horizontal offset between hip and knee, relative to leg length.
    # A large offset means the hip has drifted far in front of (or behind)
    # the knee, which in a real lunge correlates strongly with the torso
    # pitching forward/backward instead of staying upright.
    MAX_TORSO_LEAN_RATIO = 0.35

    # --- Back-knee depth heuristic ---
    # Vertical drop of the hip relative to leg length. In a well-formed
    # lunge the hip drops close to knee height, which (given a stable
    # front-knee angle) implies the trailing/back knee has also bent
    # correctly rather than staying locked/straight.
    MIN_HIP_DROP_RATIO = 0.28

    # --- Balance heuristic ---
    # Frame-to-frame horizontal drift of the ankle, relative to leg
    # length. Large lateral wobble of the planted foot indicates the
    # person is losing balance rather than holding the lunge steady.
    MAX_ANKLE_DRIFT_RATIO = 0.12

    def __init__(self):
        super().__init__("Lunges")
        self.calculator = AngleCalculator()

        # Default to a known, safe starting stage.
        self.stage = "STANDING"
        self.feedback = "Stand Straight"

        # Internal stability tracking (not part of the public output contract).
        self._standing_streak = 0
        self._lunge_streak = 0
        self._last_angle = None
        self._last_ankle = None
        self._last_hip = None

        # Tracks whether full lunge depth was reached during the current
        # standing -> lunge -> standing cycle, so partial reps aren't counted.
        self._depth_reached_this_rep = False

        # Frame-based cooldown to prevent double-counting a single rep.
        self._cooldown_counter = 0

    def update(self, hip, knee, ankle):
        """
        3 positional args, exactly this order:
        (hip, knee, ankle) — all (x, y) tuples from get_best_leg().
        """

        # --- 1. Validate landmark tracking quality (balance pre-check) ---
        if not self._landmarks_are_valid(hip, knee, ankle):
            self.feedback = "Balance Your Body"
            self._last_ankle = None
            self._last_hip = None
            return self._build_result(angle=0.0)

        angle = self.calculator.calculate(hip, knee, ankle)

        # --- 2. Anti camera-shake: reject sudden, physically-implausible jumps ---
        if self._is_jitter(angle):
            self.feedback = "Hold Steady"
            self._last_angle = angle
            self._last_ankle = ankle
            self._last_hip = hip
            return self._build_result(angle)

        # --- 3. Balance check: sudden lateral drift of the planted foot ---
        if self._is_off_balance(hip, ankle):
            self.feedback = "Balance Your Body"
            self._last_angle = angle
            self._last_ankle = ankle
            self._last_hip = hip
            return self._build_result(angle)

        self._last_angle = angle
        self._last_ankle = ankle
        self._last_hip = hip

        # --- 4. Tick down the rep cooldown ---
        if self._cooldown_counter > 0:
            self._cooldown_counter -= 1

        # --- 5. Classify the current frame's pose (front knee angle) ---
        pose = self._classify_pose(angle)

        # --- 6. Update stability streaks (hysteresis) ---
        self._update_streaks(pose)

        # --- 7. Stage transition state machine (incorporates torso + back-knee) ---
        self._process_stage_transitions(pose, angle, hip, ankle, knee)

        return self._build_result(angle)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _landmarks_are_valid(self, hip, knee, ankle):
        """Basic sanity check that all three points were tracked properly."""
        for point in (hip, knee, ankle):
            if point is None:
                return False
            if len(point) != 2:
                return False
            x, y = point
            if x is None or y is None:
                return False
            if math.isnan(x) or math.isnan(y):
                return False
        return True

    def _is_jitter(self, angle):
        """Reject implausible frame-to-frame angle jumps caused by MediaPipe noise."""
        if self._last_angle is None:
            return False
        return abs(angle - self._last_angle) > self.MAX_FRAME_TO_FRAME_JUMP

    def _is_off_balance(self, hip, ankle):
        """
        Flag sudden lateral drift of the planted ankle relative to leg
        length as a loss of balance, rather than a legitimate step.
        """
        if self._last_ankle is None:
            return False

        leg_length = self._distance(hip, ankle)
        if leg_length < self.MIN_LEG_LENGTH:
            return False

        drift = abs(ankle[0] - self._last_ankle[0])
        return (drift / leg_length) > self.MAX_ANKLE_DRIFT_RATIO

    def _classify_pose(self, angle):
        """Classify the current frame as STANDING, LUNGE, or TRANSITION."""
        if angle >= self.STANDING_ANGLE_THRESHOLD:
            return "STANDING"
        if self.LUNGE_ANGLE_MIN <= angle <= self.LUNGE_ANGLE_MAX:
            return "LUNGE"
        return "TRANSITION"

    def _update_streaks(self, pose):
        """Maintain consecutive-frame counters used to debounce stage changes."""
        if pose == "STANDING":
            self._standing_streak += 1
            self._lunge_streak = 0
        elif pose == "LUNGE":
            self._lunge_streak += 1
            self._standing_streak = 0
        else:
            # In the transition zone we don't accumulate stability toward
            # either extreme; this keeps quick, noisy oscillations from
            # ever reaching the required streak length.
            self._standing_streak = 0
            self._lunge_streak = 0

    def _stride_ratio(self, hip, knee, ankle):
        """
        Approximate how far the front foot has stepped forward relative to
        leg length. Used to catch shallow / lazy lunges where the knee angle
        looks correct but the stance is too narrow. (Front knee / stance check)
        """
        leg_length = self._distance(hip, knee) + self._distance(knee, ankle)
        if leg_length < self.MIN_LEG_LENGTH:
            return 0.0
        stride = abs(ankle[0] - hip[0])
        return stride / leg_length

    def _torso_lean_ratio(self, hip, knee, ankle):
        """
        Approximate torso lean using the horizontal offset between the hip
        and the knee, relative to leg length. A hip that sits far ahead of
        (or behind) the knee usually means the torso is pitching instead of
        staying upright over the hips. (Torso check)
        """
        leg_length = self._distance(hip, knee) + self._distance(knee, ankle)
        if leg_length < self.MIN_LEG_LENGTH:
            return 0.0
        offset = abs(hip[0] - knee[0])
        return offset / leg_length

    def _hip_drop_ratio(self, hip, knee, ankle):
        """
        Approximate back-knee bend depth using how far the hip has dropped
        vertically relative to overall leg length. A shallow hip drop with
        an otherwise valid front-knee angle usually means the trailing/back
        knee never bent properly. (Back knee check)
        """
        leg_length = self._distance(hip, knee) + self._distance(knee, ankle)
        if leg_length < self.MIN_LEG_LENGTH:
            return 0.0
        drop = abs(hip[1] - knee[1])
        return drop / leg_length

    @staticmethod
    def _distance(point_a, point_b):
        return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])

    def _process_stage_transitions(self, pose, angle, hip, ankle, knee):
        """Core standing -> lunge -> standing state machine with posture checks."""

        # STANDING -> LUNGE
        if self.stage == "STANDING" and pose == "LUNGE":
            if self._lunge_streak >= self.STABILITY_FRAMES_REQUIRED:
                stride_ratio = self._stride_ratio(hip, knee, ankle)
                torso_ratio = self._torso_lean_ratio(hip, knee, ankle)
                hip_drop_ratio = self._hip_drop_ratio(hip, knee, ankle)

                if stride_ratio < self.MIN_STRIDE_RATIO:
                    # Front knee angle looks right but the stance is too shallow.
                    self.feedback = "Step Farther"
                    return

                if torso_ratio > self.MAX_TORSO_LEAN_RATIO:
                    # Stance is fine but the hip (torso) has drifted too far
                    # forward/backward over the front knee.
                    self.feedback = "Keep Torso Upright"
                    return

                if hip_drop_ratio < self.MIN_HIP_DROP_RATIO:
                    # Front knee is bent enough but the hip hasn't dropped,
                    # meaning the back knee likely hasn't bent enough either.
                    self.feedback = "Lower More"
                    return

                self.stage = "LUNGE"
                self._depth_reached_this_rep = True
                self.feedback = "Excellent Lunge"
            return

        # LUNGE -> STANDING (closes out a rep, subject to cooldown)
        if self.stage == "LUNGE" and pose == "STANDING":
            if self._standing_streak >= self.STABILITY_FRAMES_REQUIRED:
                self.stage = "STANDING"

                if self._depth_reached_this_rep and self._cooldown_counter == 0:
                    self.reps += 1
                    self._cooldown_counter = self.REP_COOLDOWN_FRAMES
                    self.feedback = "Excellent Lunge"
                else:
                    self.feedback = "Stand Up"

                self._depth_reached_this_rep = False
            return

        # Still moving down toward a lunge, not yet stable/deep enough.
        if self.stage == "STANDING" and pose == "TRANSITION":
            self.feedback = "Lower More"
            return

        # Currently down in a lunge but angle drifted out of the valid window.
        if self.stage == "LUNGE" and pose == "TRANSITION":
            if angle > self.LUNGE_ANGLE_MAX:
                self.feedback = "Stand Up"
            else:
                self.feedback = "Lower More"
            return

        # Holding steady in a recognized position — re-check posture even
        # while stationary in the lunge so lingering form errors surface.
        if pose == "STANDING":
            self.feedback = "Stand Straight"
        elif pose == "LUNGE":
            torso_ratio = self._torso_lean_ratio(hip, knee, ankle)
            hip_drop_ratio = self._hip_drop_ratio(hip, knee, ankle)

            if torso_ratio > self.MAX_TORSO_LEAN_RATIO:
                self.feedback = "Keep Torso Upright"
            elif hip_drop_ratio < self.MIN_HIP_DROP_RATIO:
                self.feedback = "Lower More"
            else:
                self.feedback = "Excellent Lunge"
        else:
            self.feedback = "Good Form"

    def _build_result(self, angle):
        """Assemble the unchanged output contract expected by the rest of the app."""
        return {
            "exercise": self.name,
            "angle": round(angle, 1),
            "reps": self.reps,
            "stage": self.stage,
            "feedback": self.feedback,
        }