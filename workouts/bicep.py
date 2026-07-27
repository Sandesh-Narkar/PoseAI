"""
bicep.py
---------
AI Bicep Curl Counter with real-time form correction.

Rep-counting logic (stage transitions, stability filtering, cooldown,
and the rep increment itself) is completely unchanged from the
original implementation. Everything else in this file is an
additional, non-invasive form-analysis layer that inspects the same
shoulder/elbow/wrist landmarks already being passed in and produces
professional, actionable coaching feedback:

    * Elbow drifting        - elbow moving away from its anchored
                               position over the course of a rep
    * Elbow away from body   - elbow flaring outward from the torso
    * Full arm extension     - arm not fully straightening at the
                               bottom (surfaced via the existing
                               "Straighten Your Arm" mid-range message)
    * Full curl               - arm not fully curling at the top
                               (surfaced via the existing
                               "Curl Higher" mid-range message)
    * Body swinging           - shoulder translating frame-to-frame
                               instead of staying planted
    * Wrist alignment         - forearm/wrist twisting out of the
                               natural curl plane
    * Controlled movement     - curling/lowering too fast (momentum
                               instead of muscle control)

All thresholds are heuristic and tuned for normalized (0-1) landmark
coordinates - they are estimates for coaching purposes, not a
biomechanical measurement.
"""

import math

from workouts.base_workout import BaseWorkout
from core.angle_calculator import AngleCalculator


class BicepWorkout(BaseWorkout):

    # Elbow angle above which the arm is considered fully straight (DOWN).
    DOWN_ANGLE_THRESHOLD = 160

    # Elbow angle below which the arm is considered fully curled (UP).
    UP_ANGLE_THRESHOLD = 40

    # Number of consecutive frames the arm must stay past a threshold
    # before that position is accepted as "stable". This filters out
    # MediaPipe jitter and camera shake that would otherwise flip the
    # stage back and forth on a single noisy frame.
    REQUIRED_STABLE_FRAMES = 3

    # After a rep is counted, ignore new reps for this many frames so a
    # single fast wobble at the top of the curl can't be double-counted.
    REP_COOLDOWN_FRAMES = 10

    # ---- Form-correction thresholds (all scale-normalized against the
    #      current upper-arm length, i.e. shoulder-to-elbow distance,
    #      so they hold up across different distances from the camera) --
    ELBOW_DRIFT_RATIO_THRESHOLD = 0.35     # elbow moved from its anchor
    ELBOW_AWAY_RATIO_THRESHOLD = 0.55      # elbow horizontal flare vs torso
    SHOULDER_SWING_RATIO_THRESHOLD = 0.12  # frame-to-frame shoulder motion
    WRIST_MISALIGN_RATIO_THRESHOLD = 1.6   # wrist horizontal offset vs elbow
    ANGULAR_VELOCITY_THRESHOLD = 18.0      # degrees/frame = too fast

    # Consecutive frames a fault must persist before it's surfaced, to
    # avoid flickering feedback caused by single noisy frames.
    FAULT_STABLE_FRAMES = 3

    def __init__(self):

        super().__init__("Bicep Curl")

        self.calculator = AngleCalculator()

        # Consecutive-frame counters used for stage stability checks.
        self._down_frame_count = 0
        self._up_frame_count = 0

        # Frames remaining before another rep is allowed to be counted.
        self._cooldown_frames_remaining = 0

        # ---- Form-analysis state (display/coaching only - never
        #      touches stage/rep logic) -----------------------------
        self._prev_shoulder = None
        self._prev_angle = None

        # Elbow position (relative to shoulder) captured the moment the
        # arm becomes stable at the bottom of a rep - used as the
        # "anchor" that the elbow should stay close to while curling.
        self._elbow_anchor_offset = None

        # Consecutive-frame counters for each fault, so a fault must
        # persist briefly before it's surfaced to the user.
        self._swing_fault_frames = 0
        self._speed_fault_frames = 0
        self._elbow_away_fault_frames = 0
        self._elbow_drift_fault_frames = 0
        self._wrist_fault_frames = 0

    # ------------------------------------------------------------------ #
    # FORM-CORRECTION HELPERS
    # ------------------------------------------------------------------ #

    @staticmethod
    def _xy(point):
        """Extract (x, y) from a landmark that may carry extra fields (z, visibility, ...)."""
        return float(point[0]), float(point[1])

    @staticmethod
    def _distance(point_a, point_b):
        ax, ay = BicepWorkout._xy(point_a)
        bx, by = BicepWorkout._xy(point_b)
        return math.hypot(ax - bx, ay - by)

    def _analyze_form(self, shoulder, elbow, wrist, angle, just_became_down_stable):
        """
        Run all real-time form checks for the current frame and return
        the single highest-priority fault message, or None if form
        looks clean. Purely additive/observational - never changes
        self.stage, self.reps, or the stability counters above.
        """
        shoulder_xy = self._xy(shoulder)
        elbow_xy = self._xy(elbow)
        wrist_xy = self._xy(wrist)

        # Upper-arm length is the scale reference for every ratio below.
        upper_arm_length = max(self._distance(shoulder, elbow), 1e-6)

        # Refresh the elbow anchor every time the arm settles into a
        # stable bottom position - that's the "home" elbow position the
        # user should keep close to for the rest of the rep.
        if just_became_down_stable or self._elbow_anchor_offset is None:
            self._elbow_anchor_offset = (
                elbow_xy[0] - shoulder_xy[0],
                elbow_xy[1] - shoulder_xy[1],
            )

        # ---- 1) Elbow drifting: how far has the elbow moved (relative
        #      to the shoulder) from its anchored position? -----------
        anchor_dx = (elbow_xy[0] - shoulder_xy[0]) - self._elbow_anchor_offset[0]
        anchor_dy = (elbow_xy[1] - shoulder_xy[1]) - self._elbow_anchor_offset[1]
        elbow_drift_ratio = math.hypot(anchor_dx, anchor_dy) / upper_arm_length

        if elbow_drift_ratio > self.ELBOW_DRIFT_RATIO_THRESHOLD:
            self._elbow_drift_fault_frames += 1
        else:
            self._elbow_drift_fault_frames = 0

        # ---- 2) Elbow moving away from the body: horizontal flare of
        #      the elbow relative to the torso/shoulder. ----------------
        elbow_away_ratio = abs(elbow_xy[0] - shoulder_xy[0]) / upper_arm_length

        if elbow_away_ratio > self.ELBOW_AWAY_RATIO_THRESHOLD:
            self._elbow_away_fault_frames += 1
        else:
            self._elbow_away_fault_frames = 0

        # ---- 3) Body swinging: how much did the shoulder itself move
        #      since the previous frame (it should stay planted)? ------
        if self._prev_shoulder is not None:
            shoulder_move_ratio = self._distance(shoulder, self._prev_shoulder) / upper_arm_length
        else:
            shoulder_move_ratio = 0.0

        if shoulder_move_ratio > self.SHOULDER_SWING_RATIO_THRESHOLD:
            self._swing_fault_frames += 1
        else:
            self._swing_fault_frames = 0

        # ---- 4) Wrist alignment: the wrist shouldn't swing sideways
        #      further out than the forearm's natural path implies. ----
        elbow_offset_from_shoulder = abs(elbow_xy[0] - shoulder_xy[0])
        wrist_offset_from_elbow = abs(wrist_xy[0] - elbow_xy[0])
        reference_offset = max(elbow_offset_from_shoulder, upper_arm_length * 0.1)
        wrist_misalign_ratio = wrist_offset_from_elbow / reference_offset

        if wrist_misalign_ratio > self.WRIST_MISALIGN_RATIO_THRESHOLD:
            self._wrist_fault_frames += 1
        else:
            self._wrist_fault_frames = 0

        # ---- 5) Controlled movement: angular velocity of the elbow
        #      angle - fast, jerky reps rely on momentum, not muscle. --
        if self._prev_angle is not None:
            angular_velocity = abs(angle - self._prev_angle)
        else:
            angular_velocity = 0.0

        if angular_velocity > self.ANGULAR_VELOCITY_THRESHOLD:
            self._speed_fault_frames += 1
        else:
            self._speed_fault_frames = 0

        # Persist state for next frame's deltas.
        self._prev_shoulder = shoulder
        self._prev_angle = angle

        # ---- Resolve to the single highest-priority confirmed fault ---
        if self._swing_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Avoid Swinging"
        if self._speed_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Slow Down - Control The Rep"
        if self._elbow_away_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Keep Elbows Close"
        if self._elbow_drift_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Keep Elbow Steady"
        if self._wrist_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Align Your Wrist"

        return None

    # ------------------------------------------------------------------ #
    # MAIN UPDATE
    # ------------------------------------------------------------------ #

    def update(self, shoulder, elbow, wrist):

        angle = self.calculator.calculate(
            shoulder,
            elbow,
            wrist
        )

        # Tick down the rep cooldown every frame, regardless of angle.
        if self._cooldown_frames_remaining > 0:
            self._cooldown_frames_remaining -= 1

        rep_counted_this_frame = False

        if angle > self.DOWN_ANGLE_THRESHOLD:
            # Arm is (close to) fully straight - build up DOWN stability
            # and reset the opposite counter so a single noisy frame
            # can't carry over stability from the other end of the curl.
            self._down_frame_count += 1
            self._up_frame_count = 0

            if self._down_frame_count >= self.REQUIRED_STABLE_FRAMES:
                self.stage = "DOWN"
                self.feedback = "Good Form"
            else:
                self.feedback = "Hold Steady"

        elif angle < self.UP_ANGLE_THRESHOLD:
            # Arm is (close to) fully curled - build up UP stability.
            self._up_frame_count += 1
            self._down_frame_count = 0

            if self._up_frame_count >= self.REQUIRED_STABLE_FRAMES:
                # Only count the rep if:
                #   - the arm was previously stable in the DOWN position
                #     (full range of motion, not a half-rep), and
                #   - the cooldown from a previous rep has expired.
                if self.stage == "DOWN" and self._cooldown_frames_remaining == 0:
                    self.stage = "UP"
                    self.reps += 1
                    self._cooldown_frames_remaining = self.REP_COOLDOWN_FRAMES
                    self.feedback = "Excellent Rep!"
                    rep_counted_this_frame = True
                else:
                    self.stage = "UP"
                    if not rep_counted_this_frame:
                        self.feedback = "Good Form"
            else:
                self.feedback = "Hold Steady"

        else:
            # In the middle of the range of motion - not stable at
            # either end yet, so reset both stability counters and
            # give directional feedback based on which way the user
            # is moving.
            self._down_frame_count = 0
            self._up_frame_count = 0

            if self.stage == "UP":
                self.feedback = "Straighten Your Arm"
            else:
                self.feedback = "Curl Higher"

        # ---- FORM-CORRECTION LAYER (additive - does not affect the
        #      rep-counting logic above in any way) ---------------------
        just_became_down_stable = self._down_frame_count == self.REQUIRED_STABLE_FRAMES

        fault_message = self._analyze_form(
            shoulder, elbow, wrist, angle, just_became_down_stable
        )

        if rep_counted_this_frame:
            # A completed rep is always the most important thing to
            # celebrate - never overridden by a form note.
            self.feedback = "Excellent Rep!"
        elif fault_message is not None:
            self.feedback = fault_message
        elif self.feedback == "Good Form":
            # No faults detected and the arm is stable at an endpoint -
            # upgrade the generic message to a stronger compliment.
            self.feedback = "Excellent Form"
        # Otherwise keep whatever the rep-counting logic already set
        # ("Hold Steady", "Straighten Your Arm", "Curl Higher").

        return {
            "exercise": self.name,
            "angle": round(angle, 1),
            "reps": self.reps,
            "stage": self.stage,
            "feedback": self.feedback
        }