"""
crossover_toe_touch.py
-----------------------
AI Crossover Toe Touch Counter (state-machine redesign)
"""

import math

from workouts.base_workout import BaseWorkout
from core.angle_calculator import AngleCalculator


class CrossoverToeTouchWorkout(BaseWorkout):
    """
    Detects crossover toe-touch repetitions with a five-node state
    machine driven by torso-relative wrist crossing, instead of raw
    wrist-to-foot distance:

        CENTER -> RIGHT_CROSS -> CENTER -> LEFT_CROSS -> CENTER (= 1 rep)

    Core signals used:
      * Body center        - a blended midpoint of the shoulders and
                              hips, used as the vertical reference
                              line a wrist must cross.
      * Shoulder position   - shoulder width scales every distance
                              threshold, so detection works the same
                              whether the user is close to or far
                              from a front-facing camera.
      * Wrist crossing      - each wrist's position is expressed as a
                              signed "crossed ratio" relative to its
                              *own* shoulder's side of the body
                              center. This makes the logic mirror-
                              safe regardless of landmark convention.
      * Torso forward bend  - angle at the hip formed by the
                              shoulder/hip/knee midpoints. Near 180
                              degrees means standing upright; a
                              genuine reach pulls it well below that.
      * Direction of movement - a cross (or a return to center) only
                              counts if the crossed ratio keeps
                              moving the same way across the whole
                              debounce window, which filters out
                              jitter/hover false positives.

    POSTURE ANALYSIS (additional gates on top of the state machine):
      * Hand reaches opposite foot - the active wrist must get close
                              enough (vertically) to the OPPOSITE
                              ankle before a cross is confirmed,
                              otherwise the reach is too shallow.
      * Body twist          - genuine crossover reaches visibly
                              foreshorten the shoulder line (from a
                              front-facing camera) as the torso
                              rotates. Current shoulder width is
                              compared against a resting baseline
                              captured while standing upright at
                              CENTER; insufficient foreshortening
                              means the user reached with the arm
                              only, without actually twisting.
      * Standing posture     - unchanged: the torso angle must return
                              close to upright before a release back
                              to CENTER is accepted.
      * Alternate sides       - the state machine already enforces
                              right-then-left ordering; this adds an
                              explicit fault when the user re-attempts
                              the side they just completed instead of
                              switching to the other side.
    """

    # ---- Body-scale reference --------------------------------------
    MIN_SHOULDER_WIDTH = 1e-3
    MIN_LEG_LENGTH = 1e-3

    # ---- Wrist crossing thresholds (fraction of shoulder width) ----
    # Hysteresis band: a cross is only registered once the ratio
    # exceeds CROSS_ENTER_RATIO, and isn't considered "released" back
    # to center until it drops below the smaller CROSS_EXIT_RATIO.
    # The gap between the two prevents flicker when a wrist hovers
    # near a single boundary value.
    CROSS_ENTER_RATIO = 0.40
    CROSS_EXIT_RATIO = 0.15

    # ---- Torso forward-bend thresholds (degrees) --------------------
    # Angle at the hip formed by shoulder_mid -> hip_mid -> knee_mid.
    # ~180 degrees means standing straight; bending forward to reach
    # across pulls this angle down noticeably.
    MAX_BEND_ANGLE_FOR_CROSS = 150
    MIN_STANDING_ANGLE = 165

    # ---- Reach-depth heuristic ("Hand reaches opposite foot") -------
    # Max allowed vertical distance between the active wrist and the
    # OPPOSITE ankle, normalized by leg length, for the reach to count
    # as genuinely low enough (i.e. actually toward the foot).
    REACH_DEPTH_RATIO_MAX = 0.55

    # ---- Body-twist heuristic ------------------------------------------
    # Ratio of current (foreshortened) shoulder width to the resting
    # baseline shoulder width captured while standing upright at
    # CENTER. A genuine twist noticeably shrinks the apparent shoulder
    # width from a front-facing camera; values close to 1.0 mean the
    # torso barely rotated at all.
    TWIST_WIDTH_RATIO_MAX = 0.88
    BASELINE_WIDTH_EMA_ALPHA = 0.2

    # ---- Debounce: consecutive stable frames required ---------------
    REQUIRED_CROSS_FRAMES = 4
    REQUIRED_CENTER_FRAMES = 4

    # ---- Direction-of-movement tolerance -----------------------------
    # Small allowance for landmark jitter so a genuinely monotonic
    # reach/return isn't reset by a single noisy frame.
    MOVEMENT_NOISE_TOLERANCE = 0.02

    # ---- Post-rep cooldown --------------------------------------------
    # After a full rep, ignore new cross attempts for a few frames so
    # a fast bounce at center can't double-count.
    REP_COOLDOWN_FRAMES = 10

    def __init__(self):

        super().__init__("Crossover Toe Touches")

        self.calculator = AngleCalculator()

        # "CENTER"      - standing upright, wrists not crossed
        # "RIGHT_CROSS" - right wrist has crossed to the left side
        # "LEFT_CROSS"  - left wrist has crossed to the right side
        self.stage = "CENTER"

        # Whether the right-side cross has already been completed in
        # the current rep. When True, the machine is waiting on
        # CENTER for a left cross to close out the rep.
        self._right_side_done = False

        # Shared debounce state. Only one of "counting toward a
        # cross" or "counting toward center" is ever active at a
        # time, so a single pair of counters is reused across stages
        # and reset on every transition.
        self._debounce_frames = 0
        self._debounce_anchor_ratio = None

        self._cooldown_frames_remaining = 0

        # Resting shoulder-width baseline, captured (as an EMA) while
        # standing upright at CENTER with both wrists uncrossed. Used
        # as the reference for the body-twist check.
        self._baseline_shoulder_width = None

    def reset(self):

        super().reset()

        self.stage = "CENTER"
        self._right_side_done = False
        self._debounce_frames = 0
        self._debounce_anchor_ratio = None
        self._cooldown_frames_remaining = 0
        self._baseline_shoulder_width = None

    @staticmethod
    def _midpoint(point_a, point_b):
        return (
            (point_a[0] + point_b[0]) / 2,
            (point_a[1] + point_b[1]) / 2,
        )

    @staticmethod
    def _distance(point_a, point_b):
        return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])

    @staticmethod
    def _sign(value):
        if value > 0:
            return 1.0
        if value < 0:
            return -1.0
        return 0.0

    def _reset_debounce(self):
        self._debounce_frames = 0
        self._debounce_anchor_ratio = None

    def _update_baseline_width(self, shoulder_width, right_crossed_ratio,
                                left_crossed_ratio, torso_angle):
        """
        Refresh the resting shoulder-width baseline whenever the user
        is standing upright at CENTER with both wrists clearly
        uncrossed. Used as the reference point for the body-twist
        check - a real crossover reach visibly foreshortens the
        shoulder line relative to this resting value.
        """
        if (
            self.stage == "CENTER"
            and torso_angle > self.MIN_STANDING_ANGLE
            and right_crossed_ratio < self.CROSS_EXIT_RATIO
            and left_crossed_ratio < self.CROSS_EXIT_RATIO
        ):
            if self._baseline_shoulder_width is None:
                self._baseline_shoulder_width = shoulder_width
            else:
                self._baseline_shoulder_width = (
                    self.BASELINE_WIDTH_EMA_ALPHA * shoulder_width
                    + (1 - self.BASELINE_WIDTH_EMA_ALPHA) * self._baseline_shoulder_width
                )

    def update(
        self,
        left_shoulder,
        right_shoulder,
        left_hip,
        right_hip,
        left_knee,
        right_knee,
        left_ankle,
        right_ankle,
        left_wrist,
        right_wrist,
    ):
        shoulder_mid = self._midpoint(left_shoulder, right_shoulder)
        hip_mid = self._midpoint(left_hip, right_hip)
        knee_mid = self._midpoint(left_knee, right_knee)

        # Blended body center: averaging the shoulder and hip
        # midpoints gives a stable vertical reference line that
        # doesn't shift around just because the arms are moving.
        center_x = (shoulder_mid[0] + hip_mid[0]) / 2

        shoulder_width = self._distance(left_shoulder, right_shoulder)
        scale = max(shoulder_width, self.MIN_SHOULDER_WIDTH)

        # Torso forward-bend angle (vertex at hip_mid).
        torso_angle = self.calculator.calculate(shoulder_mid, hip_mid, knee_mid)

        # Each wrist's "crossed ratio": positive means it has moved
        # past the body center toward the *opposite* shoulder's side,
        # scaled by shoulder width so detection is distance-
        # independent. Expressing it relative to each wrist's own
        # resting shoulder side keeps this mirror-safe.
        right_side_sign = self._sign(right_shoulder[0] - center_x) or 1.0
        left_side_sign = self._sign(left_shoulder[0] - center_x) or -1.0

        right_crossed_ratio = (-right_side_sign * (right_wrist[0] - center_x)) / scale
        left_crossed_ratio = (-left_side_sign * (left_wrist[0] - center_x)) / scale

        # Reference leg length for the reach-depth check, averaged
        # across both legs so it stays stable even mid-reach.
        leg_length = (
            self._distance(left_hip, left_knee) + self._distance(left_knee, left_ankle)
            + self._distance(right_hip, right_knee) + self._distance(right_knee, right_ankle)
        ) / 2

        self._update_baseline_width(
            shoulder_width, right_crossed_ratio, left_crossed_ratio, torso_angle
        )

        if self._cooldown_frames_remaining > 0:
            self._cooldown_frames_remaining -= 1

        if self.stage == "CENTER":
            self._handle_center(
                right_crossed_ratio, left_crossed_ratio, torso_angle,
                shoulder_width, leg_length, right_wrist, left_wrist,
                right_ankle, left_ankle,
            )
        elif self.stage == "RIGHT_CROSS":
            self._handle_active_cross(
                active_ratio=right_crossed_ratio,
                torso_angle=torso_angle,
                completing_side="RIGHT",
            )
        else:  # "LEFT_CROSS"
            self._handle_active_cross(
                active_ratio=left_crossed_ratio,
                torso_angle=torso_angle,
                completing_side="LEFT",
            )

        return self._build_result()

    def _handle_center(
        self, right_crossed_ratio, left_crossed_ratio, torso_angle,
        shoulder_width, leg_length, right_wrist, left_wrist,
        right_ankle, left_ankle,
    ):
        """
        From CENTER, wait for whichever side is expected next
        (right first, then left) to cross past the body's vertical
        center line with a consistent, sustained reaching motion.
        """

        expected_side = "LEFT" if self._right_side_done else "RIGHT"
        active_ratio = (
            left_crossed_ratio if expected_side == "LEFT" else right_crossed_ratio
        )
        other_ratio = (
            right_crossed_ratio if expected_side == "LEFT" else left_crossed_ratio
        )
        active_wrist = left_wrist if expected_side == "LEFT" else right_wrist
        # "Hand reaches opposite foot": right hand crosses toward the
        # LEFT foot, left hand crosses toward the RIGHT foot.
        target_ankle = right_ankle if expected_side == "LEFT" else left_ankle

        if self._cooldown_frames_remaining > 0:
            self._reset_debounce()
            self.feedback = "Get Ready"
            return

        # ---- Alternate-sides check: the user is re-attempting the
        #      side they just completed instead of switching. --------
        if other_ratio >= self.CROSS_ENTER_RATIO and active_ratio < self.CROSS_ENTER_RATIO:
            self._reset_debounce()
            self.feedback = "Alternate Sides"
            return

        if active_ratio < self.CROSS_ENTER_RATIO:
            # Wrist hasn't reached far enough across the center line
            # yet - ignore small arm movements entirely.
            self._reset_debounce()
            self.feedback = (
                "Cross Right Hand to the Left"
                if expected_side == "RIGHT"
                else "Cross Left Hand to the Right"
            )
            return

        # Wrist is past the entry threshold. Require the crossing
        # motion to be consistent (not retreating) across the whole
        # debounce window before accepting it as real.
        if self._debounce_anchor_ratio is None:
            self._debounce_anchor_ratio = active_ratio
            self._debounce_frames = 1
        elif active_ratio >= self._debounce_anchor_ratio - self.MOVEMENT_NOISE_TOLERANCE:
            self._debounce_frames += 1
            self._debounce_anchor_ratio = min(self._debounce_anchor_ratio, active_ratio)
        else:
            # Wrist pulled back - restart the streak instead of
            # counting jitter as a sustained reach.
            self._debounce_anchor_ratio = active_ratio
            self._debounce_frames = 1

        if self._debounce_frames < self.REQUIRED_CROSS_FRAMES:
            self.feedback = "Hold the Reach"
            return

        if torso_angle > self.MAX_BEND_ANGLE_FOR_CROSS:
            # Plenty of crossing distance, but not enough forward
            # bend - likely an arm-only swing rather than a genuine
            # crossover reach.
            self.feedback = "Bend Forward and Reach Across"
            return

        # ---- Hand-reaches-opposite-foot check --------------------------
        if leg_length > self.MIN_LEG_LENGTH:
            reach_gap = abs(active_wrist[1] - target_ankle[1])
            reach_ratio = reach_gap / leg_length
            if reach_ratio > self.REACH_DEPTH_RATIO_MAX:
                self.feedback = "Reach Lower"
                return

        # ---- Body-twist check --------------------------------------------
        if self._baseline_shoulder_width is not None and self._baseline_shoulder_width > self.MIN_SHOULDER_WIDTH:
            twist_ratio = shoulder_width / self._baseline_shoulder_width
            if twist_ratio > self.TWIST_WIDTH_RATIO_MAX:
                self.feedback = "Twist More"
                return

        # Confirmed: genuine, sustained, bent-forward crossover reach
        # with sufficient depth and torso twist.
        self.stage = "RIGHT_CROSS" if expected_side == "RIGHT" else "LEFT_CROSS"
        self._reset_debounce()
        self.feedback = "Good Cross"

    def _handle_active_cross(self, active_ratio, torso_angle, completing_side):
        """
        From RIGHT_CROSS or LEFT_CROSS, require the user to fully
        return to an upright, hands-uncrossed CENTER position before
        the next side (or the rep) can be registered.
        """

        if active_ratio > self.CROSS_EXIT_RATIO:
            # Still crossed - keep waiting, and don't let a released
            # streak that hasn't actually reached the exit band count
            # toward the debounce window.
            self._reset_debounce()
            self.feedback = "Return to Center"
            return

        # Wrist is back inside the release band. Require the
        # retreating motion to stay consistent (not re-crossing)
        # across the whole debounce window.
        if self._debounce_anchor_ratio is None:
            self._debounce_anchor_ratio = active_ratio
            self._debounce_frames = 1
        elif active_ratio <= self._debounce_anchor_ratio + self.MOVEMENT_NOISE_TOLERANCE:
            self._debounce_frames += 1
            self._debounce_anchor_ratio = max(self._debounce_anchor_ratio, active_ratio)
        else:
            self._debounce_anchor_ratio = active_ratio
            self._debounce_frames = 1

        if self._debounce_frames < self.REQUIRED_CENTER_FRAMES:
            self.feedback = "Return to Center"
            return

        if torso_angle < self.MIN_STANDING_ANGLE:
            # Hands have released but the torso hasn't straightened
            # back up yet - not a full return to center (standing
            # posture check).
            self.feedback = "Stand Up Straight"
            return

        # Confirmed: fully released and upright again.
        self.stage = "CENTER"
        self._reset_debounce()

        if completing_side == "RIGHT":
            self._right_side_done = True
            self.feedback = "Now Cross to the Left"
        else:
            self._right_side_done = False
            self.reps += 1
            self._cooldown_frames_remaining = self.REP_COOLDOWN_FRAMES
            self.feedback = "Excellent Rep"

    def _build_result(self):

        return {
            "exercise": self.name,
            "reps": self.reps,
            "stage": self.stage,
            "feedback": self.feedback,
        }