"""
workouts/triceps_pushdown.py
------------------------------
Triceps Pushdown workout logic.

The public update() signature is unchanged: update(self, shoulder, elbow, wrist)
— a single (shoulder, elbow, wrist) landmark set, exactly as before.

Because only one arm's three landmarks are available per call (no
opposite arm, no torso/hip landmarks), the additional posture checks
below are approximated purely from how shoulder/elbow/wrist move
relative to each other and to their own baseline position over time:

    * Elbows fixed    - the elbow's position is captured as a baseline
                         while resting at the top (BENT) of the
                         movement, then compared frame-to-frame during
                         the push; drifting too far (elbow flaring out
                         or swinging) breaks form.
    * Full extension   - the bottom of the pushdown must reach a
                          strict, near-straight-arm angle before a rep
                          is granted, not just the looser classification
                          threshold.
    * Wrist position    - the wrist's lateral offset from the
                           shoulder-elbow line is checked so a rep
                           isn't rewarded if the wrist flicks/rotates
                           sideways instead of tracking straight down.
    * Body movement     - the shoulder's own position is compared to
                           its baseline; a shoulder that drifts a lot
                           usually means the torso is swinging/using
                           momentum rather than isolating the triceps.

Since coaching feedback is limited to a fixed vocabulary, elbow
drift, wrist misalignment, and shoulder (body) drift are all treated
as the same underlying fault — an unstable upper arm — and reported as
"Keep Elbows Fixed". Insufficient depth at the bottom reports "Push
Lower". Overly fast/uncontrolled movement back up reports
"Control Return". A clean, full rep reports "Excellent Rep".
"""

import math

from core.angle_calculator import AngleCalculator
from workouts.base_workout import BaseWorkout


class TricepsPushdownWorkout(BaseWorkout):

    # --- Angle thresholds (degrees) ---
    BENT_ANGLE = 90.0
    EXTENDED_ANGLE = 160.0

    # Stricter angle that must be reached at the bottom of the pushdown
    # before a rep is granted credit for full extension.
    FULL_EXTENSION_ANGLE = 165.0

    # --- Anti camera-shake: reject implausible frame-to-frame jumps ---
    MAX_ANGLE_JUMP = 40.0

    # --- Stability / debounce settings ---
    STABILITY_FRAMES_REQUIRED = 2

    # --- Cooldown after a counted rep (frames) ---
    REP_COOLDOWN_FRAMES = 10

    # --- Elbow-fixed heuristic ---
    # Elbow drift from its baseline (captured at the top/BENT position),
    # relative to upper-arm length, beyond which the elbow is considered
    # to be moving instead of staying pinned at the side.
    MAX_ELBOW_DRIFT_RATIO = 0.18

    # --- Wrist-position heuristic ---
    # Lateral offset of the wrist from the shoulder-elbow line, relative
    # to forearm length, beyond which the wrist is considered to be
    # flicking/rotating sideways instead of tracking straight down.
    MAX_WRIST_LATERAL_RATIO = 0.28

    # --- Body-movement heuristic ---
    # Shoulder drift from its baseline (captured at the top/BENT
    # position), relative to upper-arm length, beyond which the torso
    # is considered to be swinging/using momentum.
    MAX_SHOULDER_DRIFT_RATIO = 0.15

    # --- Controlled-return heuristic ---
    # Max degrees-per-frame the angle is allowed to decrease by while
    # moving from EXTENDED back toward BENT before it's flagged as an
    # uncontrolled, momentum-driven return.
    MAX_RETURN_VELOCITY = 22.0

    MIN_REF_LENGTH = 1e-3

    def __init__(self):
        super().__init__(name="Triceps Pushdown")
        self.angle_calc = AngleCalculator()

        self.stage = None
        self.feedback = "Get Ready"
        self.reps = 0
        self.angle = 0

        self._bent_streak = 0
        self._extended_streak = 0
        self._last_angle = None

        self._cooldown_counter = 0

        # Baselines captured while stable at the top (BENT) position.
        self._baseline_elbow = None
        self._baseline_shoulder = None

        # Whether the current down-phase attempt has broken form.
        self._form_broken_this_rep = False

    def update(self, shoulder, elbow, wrist):

        # --- 1. Validate landmark tracking quality ---
        if not self._landmarks_are_valid(shoulder, elbow, wrist):
            self.feedback = "Balance Your Body"
            return self._build_result(0.0)

        angle = self.angle_calc.calculate(shoulder, elbow, wrist)

        # --- 2. Anti camera-shake: reject sudden, implausible jumps ---
        if self._is_jitter(angle):
            self.feedback = "Hold Steady"
            self._last_angle = angle
            return self._build_result(angle)

        prev_angle = self._last_angle
        self._last_angle = angle
        self.angle = angle

        # --- 3. Tick down the rep cooldown ---
        if self._cooldown_counter > 0:
            self._cooldown_counter -= 1

        # --- 4. Classify the current frame's pose ---
        pose = self._classify_pose(angle)

        # --- 5. Update stability streaks (hysteresis) ---
        self._update_streaks(pose)

        # --- 6. Capture/refresh baseline elbow + shoulder position while
        #         stable at the top (BENT) of the movement ---
        if pose == "BENT" and self._bent_streak >= self.STABILITY_FRAMES_REQUIRED:
            self._baseline_elbow = elbow
            self._baseline_shoulder = shoulder
            self._form_broken_this_rep = False

        upper_arm_length = self._distance(shoulder, elbow)
        forearm_length = self._distance(elbow, wrist)

        # --- 7. Posture checks (elbow fixed, wrist position, body movement) ---
        elbow_drift = self._elbow_drift_ratio(elbow, upper_arm_length)
        wrist_lateral = self._wrist_lateral_ratio(shoulder, elbow, wrist, forearm_length)
        shoulder_drift = self._shoulder_drift_ratio(shoulder, upper_arm_length)

        form_broken_now = (
            elbow_drift > self.MAX_ELBOW_DRIFT_RATIO
            or wrist_lateral > self.MAX_WRIST_LATERAL_RATIO
            or shoulder_drift > self.MAX_SHOULDER_DRIFT_RATIO
        )
        if form_broken_now:
            self._form_broken_this_rep = True

        # --- 8. Stage transition state machine ---
        self._process_stage_transitions(pose, angle, prev_angle, form_broken_now)

        return self._build_result(angle)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _landmarks_are_valid(self, shoulder, elbow, wrist):
        for point in (shoulder, elbow, wrist):
            if point is None or len(point) != 2:
                return False
            x, y = point
            if x is None or y is None:
                return False
            if math.isnan(x) or math.isnan(y):
                return False
        return True

    def _is_jitter(self, angle):
        if self._last_angle is None:
            return False
        return abs(angle - self._last_angle) > self.MAX_ANGLE_JUMP

    def _classify_pose(self, angle):
        if angle < self.BENT_ANGLE:
            return "BENT"
        if angle > self.EXTENDED_ANGLE:
            return "EXTENDED"
        return "MIDDLE"

    def _update_streaks(self, pose):
        if pose == "BENT":
            self._bent_streak += 1
            self._extended_streak = 0
        elif pose == "EXTENDED":
            self._extended_streak += 1
            self._bent_streak = 0
        else:
            self._bent_streak = 0
            self._extended_streak = 0

    @staticmethod
    def _distance(point_a, point_b):
        return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])

    def _elbow_drift_ratio(self, elbow, upper_arm_length):
        """
        Drift of the current elbow position from its baseline (captured
        at the top of the movement), relative to upper-arm length.
        (Elbows fixed check)
        """
        if self._baseline_elbow is None or upper_arm_length < self.MIN_REF_LENGTH:
            return 0.0
        drift = self._distance(elbow, self._baseline_elbow)
        return drift / upper_arm_length

    def _shoulder_drift_ratio(self, shoulder, upper_arm_length):
        """
        Drift of the current shoulder position from its baseline
        (captured at the top of the movement), relative to upper-arm
        length. A drifting shoulder implies torso/body movement rather
        than an isolated triceps push. (Body movement check)
        """
        if self._baseline_shoulder is None or upper_arm_length < self.MIN_REF_LENGTH:
            return 0.0
        drift = self._distance(shoulder, self._baseline_shoulder)
        return drift / upper_arm_length

    def _wrist_lateral_ratio(self, shoulder, elbow, wrist, forearm_length):
        """
        Lateral (horizontal) offset of the wrist relative to the
        elbow, normalized by forearm length. A wrist that drifts far
        sideways of the elbow indicates the wrist is flicking/rotating
        instead of tracking straight down through the pushdown.
        (Wrist position check)
        """
        if forearm_length < self.MIN_REF_LENGTH:
            return 0.0
        offset = abs(wrist[0] - elbow[0])
        return offset / forearm_length

    def _process_stage_transitions(self, pose, angle, prev_angle, form_broken_now):
        """Core BENT -> EXTENDED -> BENT state machine with posture gating."""

        # --- Controlled-return check: only relevant while moving back
        #     up from EXTENDED toward BENT (angle decreasing). ---
        if self.stage == "EXTENDED" and prev_angle is not None:
            velocity = prev_angle - angle
            if velocity > self.MAX_RETURN_VELOCITY:
                self.feedback = "Control Return"
                return

        # BENT/None -> EXTENDED (closes out a rep, subject to cooldown + posture)
        if pose == "EXTENDED":
            if self._extended_streak >= self.STABILITY_FRAMES_REQUIRED:
                came_from_bent = self.stage in ("BENT", None)
                self.stage = "EXTENDED"

                if not came_from_bent:
                    self.feedback = "Excellent Rep"
                    return

                if self._form_broken_this_rep:
                    self.feedback = "Keep Elbows Fixed"
                    return

                if angle < self.FULL_EXTENSION_ANGLE:
                    self.feedback = "Push Lower"
                    return

                if self._cooldown_counter == 0:
                    self.reps += 1
                    self._cooldown_counter = self.REP_COOLDOWN_FRAMES
                    self.feedback = "Excellent Rep"
                else:
                    self.feedback = "Excellent Rep"
            return

        # -> BENT (reset for the next rep attempt)
        if pose == "BENT":
            if self._bent_streak >= self.STABILITY_FRAMES_REQUIRED:
                self.stage = "BENT"
                self._form_broken_this_rep = False
                self.feedback = "Extend Your Arm"
            return

        # MIDDLE / transition zone
        if form_broken_now:
            self.feedback = "Keep Elbows Fixed"
        elif self.stage == "EXTENDED":
            self.feedback = "Control Return"
        elif self.stage == "BENT":
            self.feedback = "Push Lower"
        else:
            self.feedback = "Get Ready"

    def _build_result(self, angle):
        return {
            "exercise": self.name,
            "angle": round(angle, 1),
            "reps": self.reps,
            "stage": self.stage,
            "feedback": self.feedback,
        }

    def reset(self):
        self.reps = 0
        self.stage = None
        self.feedback = "Get Ready"
        self.angle = 0

        self._bent_streak = 0
        self._extended_streak = 0
        self._last_angle = None
        self._cooldown_counter = 0

        self._baseline_elbow = None
        self._baseline_shoulder = None
        self._form_broken_this_rep = False