"""
goblet_squat.py
----------------
AI Goblet Squat Counter with real-time AI posture analysis.

Rep-counting logic (stage transitions, stability filtering, cooldown,
leg-symmetry gate, and the rep increment itself) is completely
unchanged from the original implementation. Everything else in this
file is an additional, non-invasive posture-analysis layer that
inspects the same hip/knee/ankle landmarks already being passed in
(no new landmarks required, so the existing call site in main.py does
not need to change) and produces professional, actionable coaching
feedback:

    * Squat depth      - flags a shallow squat that only barely
                          crosses the DOWN threshold instead of
                          reaching genuine depth
    * Back angle         - approximated (no shoulder landmark is
                          available to this workout) via the
                          hip-to-ankle horizontal offset relative to a
                          baseline captured while standing tall -
                          excessive forward drift while squatting
                          reads as the torso collapsing forward
    * Chest position      - shares the same forward-lean metric as
                          back angle, since a collapsing chest and a
                          rounding back show up together in that line
    * Knee alignment       - horizontal deviation of each knee from
                          directly above its ankle, a proxy for
                          knees caving inward (valgus)
    * Heel position         - horizontal drift of the ankles from
                          their planted baseline position, a proxy
                          for heels lifting / feet sliding as weight
                          shifts too far forward

All thresholds are heuristic and tuned for normalized (0-1) landmark
coordinates - they are estimates for coaching purposes, not a
biomechanical measurement.
"""

from workouts.base_workout import BaseWorkout
from core.angle_calculator import AngleCalculator


class GobletSquatWorkout(BaseWorkout):

    # Average knee angle above which the user is considered fully
    # standing (UP).
    UP_ANGLE_THRESHOLD = 165

    # Average knee angle below which the squat is considered deep
    # enough (DOWN). Shallow squats above this angle are rejected.
    DOWN_ANGLE_THRESHOLD = 90

    # Angle used to split the "descending from UP" mid-range feedback
    # between "keep lowering" and "almost deep enough" messages.
    MID_RANGE_MIDPOINT = (DOWN_ANGLE_THRESHOLD + UP_ANGLE_THRESHOLD) / 2

    # Number of consecutive frames the average knee angle must stay
    # past a threshold before that position is accepted as "stable".
    # This filters out MediaPipe jitter and camera shake that would
    # otherwise flip the stage back and forth on a single noisy frame.
    REQUIRED_STABLE_FRAMES = 3

    # After a rep is counted, ignore new reps for this many frames so a
    # single fast bounce at the top of the squat can't be
    # double-counted.
    REP_COOLDOWN_FRAMES = 10

    # Maximum allowed difference (in degrees) between the left and
    # right knee angles before the squat is considered unbalanced.
    # Unbalanced frames are not used to progress the stage/rep logic.
    MAX_LEG_ASYMMETRY_DEGREES = 20

    # ---- Posture-analysis thresholds -----------------------------------

    # How close to DOWN_ANGLE_THRESHOLD the angle must remain at a
    # stable DOWN position to be flagged as a shallow (not deep
    # enough) squat.
    DEPTH_QUALITY_ANGLE_MARGIN = 10

    # Deviation of the current hip->ankle forward-lean ratio from the
    # standing baseline beyond which the torso is considered
    # collapsing forward (rounding back / dropping chest).
    FORWARD_LEAN_RATIO_THRESHOLD = 0.35

    # Horizontal deviation of a knee from directly above its ankle
    # (normalized by thigh length) beyond which the knee is
    # considered caving in/out.
    KNEE_VALGUS_RATIO_THRESHOLD = 0.30

    # Horizontal drift of the ankle from its planted baseline position
    # (normalized by thigh length) beyond which the heel is considered
    # lifting / the foot sliding.
    HEEL_DRIFT_RATIO_THRESHOLD = 0.25

    # How far above UP_ANGLE_THRESHOLD the angle must be to count as
    # fully, confidently standing tall (locked out).
    STAND_LOCK_ANGLE_MARGIN = 8

    # Consecutive frames a fault must persist before it's surfaced, to
    # avoid flickering feedback caused by single noisy frames.
    FAULT_STABLE_FRAMES = 3

    def __init__(self):

        super().__init__("Goblet Squat")

        self.calculator = AngleCalculator()

        # Consecutive-frame counters used for stage stability checks.
        self._up_frame_count = 0
        self._down_frame_count = 0

        # Frames remaining before another rep is allowed to be counted.
        self._cooldown_frames_remaining = 0

        # ---- Posture-analysis state (display/coaching only - never
        #      touches stage/rep logic) -----------------------------
        # Forward-lean ratio and ankle x-positions captured the moment
        # the user first stands stably tall - the "home" reference a
        # clean squat should return to at the top.
        self._lean_baseline_ratio = None
        self._left_ankle_anchor_x = None
        self._right_ankle_anchor_x = None

        # Consecutive-frame counters for each posture fault.
        self._depth_fault_frames = 0
        self._lean_fault_frames = 0
        self._knee_fault_frames = 0
        self._heel_fault_frames = 0
        self._stand_fault_frames = 0

    def reset(self):

        super().reset()

        self._up_frame_count = 0
        self._down_frame_count = 0
        self._cooldown_frames_remaining = 0

        self._lean_baseline_ratio = None
        self._left_ankle_anchor_x = None
        self._right_ankle_anchor_x = None

        self._depth_fault_frames = 0
        self._lean_fault_frames = 0
        self._knee_fault_frames = 0
        self._heel_fault_frames = 0
        self._stand_fault_frames = 0

    # ------------------------------------------------------------------ #
    # POSTURE-ANALYSIS HELPERS
    # ------------------------------------------------------------------ #

    @staticmethod
    def _xy(point):
        """Extract (x, y) from a landmark that may carry extra fields (z, visibility, ...)."""
        return float(point[0]), float(point[1])

    @staticmethod
    def _midpoint(point_a, point_b):
        ax, ay = GobletSquatWorkout._xy(point_a)
        bx, by = GobletSquatWorkout._xy(point_b)
        return (ax + bx) / 2.0, (ay + by) / 2.0

    @staticmethod
    def _distance(point_a, point_b):
        ax, ay = GobletSquatWorkout._xy(point_a)
        bx, by = GobletSquatWorkout._xy(point_b)
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def _analyze_posture(
        self,
        left_hip, left_knee, left_ankle,
        right_hip, right_knee, right_ankle,
        just_became_up_stable, just_became_down_stable,
    ):
        """
        Run all real-time posture checks for the current frame and
        return the single highest-priority fault message, or None if
        posture looks clean. Purely additive/observational - never
        changes self.stage, self.reps, or the stability counters above.
        """
        hip_mid = self._midpoint(left_hip, right_hip)
        knee_mid = self._midpoint(left_knee, right_knee)
        ankle_mid = self._midpoint(left_ankle, right_ankle)

        thigh_length = max(self._distance(hip_mid, knee_mid), 1e-6)

        left_ankle_x, _ = self._xy(left_ankle)
        right_ankle_x, _ = self._xy(right_ankle)

        # Capture (or refresh) the standing baseline the first time the
        # legs settle into a stable, fully-extended top position - the
        # cleanest moment to trust the user's stance is neutral.
        if just_became_up_stable or self._lean_baseline_ratio is None:
            self._lean_baseline_ratio = (hip_mid[0] - ankle_mid[0]) / thigh_length
            self._left_ankle_anchor_x = left_ankle_x
            self._right_ankle_anchor_x = right_ankle_x

        # ---- Back angle / Chest position: forward-lean proxy ---------
        current_lean_ratio = (hip_mid[0] - ankle_mid[0]) / thigh_length
        lean_deviation = abs(current_lean_ratio - self._lean_baseline_ratio)

        if lean_deviation > self.FORWARD_LEAN_RATIO_THRESHOLD:
            self._lean_fault_frames += 1
        else:
            self._lean_fault_frames = 0

        # ---- Knee alignment: knee drifting away from directly above
        #      its own ankle (caving in or splaying out). ---------------
        left_knee_x, _ = self._xy(left_knee)
        right_knee_x, _ = self._xy(right_knee)

        left_valgus_ratio = abs(left_knee_x - left_ankle_x) / thigh_length
        right_valgus_ratio = abs(right_knee_x - right_ankle_x) / thigh_length
        knee_valgus_ratio = max(left_valgus_ratio, right_valgus_ratio)

        if knee_valgus_ratio > self.KNEE_VALGUS_RATIO_THRESHOLD:
            self._knee_fault_frames += 1
        else:
            self._knee_fault_frames = 0

        # ---- Heel position: ankles drifting from their planted spot -
        left_heel_drift = abs(left_ankle_x - self._left_ankle_anchor_x) / thigh_length
        right_heel_drift = abs(right_ankle_x - self._right_ankle_anchor_x) / thigh_length
        heel_drift_ratio = max(left_heel_drift, right_heel_drift)

        if heel_drift_ratio > self.HEEL_DRIFT_RATIO_THRESHOLD:
            self._heel_fault_frames += 1
        else:
            self._heel_fault_frames = 0

        # ---- Squat depth: reached DOWN but only just barely ----------
        angle = self._last_angle
        if (self.stage == "DOWN"
                and angle > self.DOWN_ANGLE_THRESHOLD - self.DEPTH_QUALITY_ANGLE_MARGIN):
            self._depth_fault_frames += 1
        else:
            self._depth_fault_frames = 0

        # ---- Fully standing: reached UP but not confidently locked ---
        if (self.stage == "UP"
                and angle < self.UP_ANGLE_THRESHOLD + self.STAND_LOCK_ANGLE_MARGIN):
            self._stand_fault_frames += 1
        else:
            self._stand_fault_frames = 0

        # ---- Resolve to the single highest-priority confirmed fault ---
        if self._knee_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Push Knees Out"
        if self._lean_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Chest Up"
        if self._heel_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Chest Up"
        if self._depth_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Go Lower"
        if self._stand_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Stand Fully"

        return None

    # ------------------------------------------------------------------ #
    # MAIN UPDATE
    # ------------------------------------------------------------------ #

    def update(
        self,
        left_hip,
        left_knee,
        left_ankle,
        right_hip,
        right_knee,
        right_ankle,
    ):

        left_angle = self.calculator.calculate(
            left_hip,
            left_knee,
            left_ankle
        )

        right_angle = self.calculator.calculate(
            right_hip,
            right_knee,
            right_ankle
        )

        angle = (left_angle + right_angle) / 2
        self._last_angle = angle

        # Tick down the rep cooldown every frame, regardless of angle.
        if self._cooldown_frames_remaining > 0:
            self._cooldown_frames_remaining -= 1

        # Body symmetry check: if one leg is bending significantly
        # more than the other, the pose is unreliable for counting a
        # rep. Surface a corrective message instead of progressing the
        # stage/rep logic on this frame.
        leg_asymmetry = abs(left_angle - right_angle)

        if leg_asymmetry > self.MAX_LEG_ASYMMETRY_DEGREES:
            self.feedback = "Control Your Movement"

            return {
                "exercise": self.name,
                "angle": round(angle, 1),
                "reps": self.reps,
                "stage": self.stage,
                "feedback": self.feedback
            }

        rep_counted_this_frame = False

        if angle > self.UP_ANGLE_THRESHOLD:
            # Fully standing - build up UP stability and reset the
            # opposite counter so a single noisy frame can't carry
            # over stability from the other end of the squat.
            self._up_frame_count += 1
            self._down_frame_count = 0

            if self._up_frame_count >= self.REQUIRED_STABLE_FRAMES:
                # Only count the rep if:
                #   - the user was previously stable in the DOWN
                #     position (full depth reached, not a shallow
                #     squat), and
                #   - the cooldown from a previous rep has expired.
                if self.stage == "DOWN" and self._cooldown_frames_remaining == 0:
                    self.stage = "UP"
                    self.reps += 1
                    self._cooldown_frames_remaining = self.REP_COOLDOWN_FRAMES
                    self.feedback = "Excellent Rep!"
                    rep_counted_this_frame = True
                else:
                    self.stage = "UP"
                    self.feedback = "Stand Straight"
            else:
                self.feedback = "Stand Straight"

        elif angle < self.DOWN_ANGLE_THRESHOLD:
            # Squat depth reached - build up DOWN stability.
            self._down_frame_count += 1
            self._up_frame_count = 0

            if self._down_frame_count >= self.REQUIRED_STABLE_FRAMES:
                self.stage = "DOWN"
                self.feedback = "Good Form"
            else:
                self.feedback = "Good Form"

        else:
            # In the middle of the range of motion - not stable at
            # either end yet, so reset both stability counters and
            # give directional feedback based on which way the user
            # is moving.
            self._up_frame_count = 0
            self._down_frame_count = 0

            if self.stage == "DOWN":
                self.feedback = "Stand Straight"
            elif angle > self.MID_RANGE_MIDPOINT:
                self.feedback = "Go Lower"
            else:
                self.feedback = "Go Lower"

        # ---- POSTURE-ANALYSIS LAYER (additive - does not affect the
        #      rep-counting logic above in any way) ----------------------
        just_became_up_stable = self._up_frame_count == self.REQUIRED_STABLE_FRAMES
        just_became_down_stable = self._down_frame_count == self.REQUIRED_STABLE_FRAMES

        fault_message = self._analyze_posture(
            left_hip, left_knee, left_ankle,
            right_hip, right_knee, right_ankle,
            just_became_up_stable, just_became_down_stable,
        )

        if rep_counted_this_frame:
            # A completed rep is always the most important thing to
            # celebrate - never overridden by a posture note.
            self.feedback = "Excellent Rep!"
        elif fault_message is not None:
            self.feedback = fault_message
        elif self.feedback in ("Good Form", "Stand Straight") and self.stage in ("UP", "DOWN"):
            # No faults detected and the body is stable at an endpoint -
            # upgrade the generic message to a stronger compliment.
            self.feedback = "Excellent Form"
        # Otherwise keep whatever the rep-counting logic already set
        # ("Go Lower", "Control Your Movement" was already returned above).

        return {
            "exercise": self.name,
            "angle": round(angle, 1),
            "reps": self.reps,
            "stage": self.stage,
            "feedback": self.feedback
        }