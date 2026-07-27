"""
pushup.py
---------
AI Push-up Counter with real-time AI posture analysis.

Rep-counting logic (stage transitions, stability filtering, cooldown,
and the rep increment itself) is completely unchanged from the
original implementation. Everything else in this file is an
additional, non-invasive posture-analysis layer that inspects the
same shoulder/elbow/wrist landmarks already being passed in (no new
landmarks are required, so the existing call site in main.py does not
need to change) and produces professional, actionable coaching
feedback:

    * Straight body     - overall torso alignment, tracked via the
                           shoulder-to-wrist line's slope relative to
                           a baseline captured at the first stable,
                           fully-extended top position
    * Hip too high       - shoulder-to-wrist line flattening beyond
                           the baseline (piking at the hips)
    * Hip too low         - shoulder-to-wrist line steepening beyond
                           the baseline (sagging at the hips)
    * Head alignment      - folded into the same body-line check,
                           since head/neck posture and torso
                           straightness both show up as deviation
                           from the established plank line
    * Chest depth          - elbow angle only marginally under the
                           DOWN threshold at the bottom (shallow reps)
    * Elbow extension      - elbow angle only marginally over the
                           UP threshold at the top (arms not locked)

All thresholds are heuristic and tuned for normalized (0-1) landmark
coordinates - they are estimates for coaching purposes, not a
biomechanical measurement.
"""

from workouts.base_workout import BaseWorkout
from core.angle_calculator import AngleCalculator


class PushupWorkout(BaseWorkout):

    # Elbow angle below which the body is considered fully lowered (DOWN).
    DOWN_ANGLE_THRESHOLD = 90

    # Elbow angle above which the arms are considered fully extended (UP).
    UP_ANGLE_THRESHOLD = 160

    # Number of consecutive frames the elbow angle must stay past a
    # threshold before that position is accepted as "stable". This
    # filters out MediaPipe jitter and camera shake that would
    # otherwise flip the stage back and forth on a single noisy frame.
    REQUIRED_STABLE_FRAMES = 3

    # After a rep is counted, ignore new reps for this many frames so a
    # single fast wobble at the top of the push-up can't be
    # double-counted.
    REP_COOLDOWN_FRAMES = 10

    # Angle used to split the "rising from DOWN" mid-range feedback
    # between "still pushing up" and "almost fully extended" messages.
    MID_RANGE_MIDPOINT = (DOWN_ANGLE_THRESHOLD + UP_ANGLE_THRESHOLD) / 2

    # ---- Posture-analysis thresholds -----------------------------------

    # How far under DOWN_ANGLE_THRESHOLD the elbow angle must be to count
    # as genuine chest depth, rather than a shallow rep that barely
    # crosses the line.
    CHEST_DEPTH_ANGLE_MARGIN = 12

    # How far over UP_ANGLE_THRESHOLD the elbow angle must be to count as
    # a fully locked-out arm at the top of the rep.
    ELBOW_LOCK_ANGLE_MARGIN = 10

    # Deviation of the current shoulder->wrist line slope from the
    # baseline (captured at the first stable, fully-extended top
    # position) beyond which the hips are considered sagging (too low).
    HIP_SAG_DEVIATION_THRESHOLD = 0.35

    # Deviation in the opposite direction beyond which the hips are
    # considered piked (too high).
    HIP_PIKE_DEVIATION_THRESHOLD = 0.35

    # A smaller deviation band that still counts as a general
    # straight-body / head-alignment fault, even if it's not extreme
    # enough to call out a specific hip direction.
    BODY_MISALIGN_DEVIATION_THRESHOLD = 0.15

    # Consecutive frames a fault must persist before it's surfaced, to
    # avoid flickering feedback caused by single noisy frames.
    FAULT_STABLE_FRAMES = 3

    def __init__(self):

        super().__init__("Push Up")

        self.calculator = AngleCalculator()

        # Consecutive-frame counters used for stage stability checks.
        self._down_frame_count = 0
        self._up_frame_count = 0

        # Frames remaining before another rep is allowed to be counted.
        self._cooldown_frames_remaining = 0

        # ---- Posture-analysis state (display/coaching only - never
        #      touches stage/rep logic) -----------------------------
        # Slope of the shoulder->wrist line captured the moment the
        # arms first become stable at the top (fully extended plank) -
        # treated as the "reference" straight-body line for this set.
        self._plank_baseline_slope = None

        # Consecutive-frame counters for each posture fault.
        self._hip_sag_fault_frames = 0
        self._hip_pike_fault_frames = 0
        self._body_misalign_fault_frames = 0
        self._chest_depth_fault_frames = 0
        self._elbow_lock_fault_frames = 0

    # ------------------------------------------------------------------ #
    # POSTURE-ANALYSIS HELPERS
    # ------------------------------------------------------------------ #

    @staticmethod
    def _xy(point):
        """Extract (x, y) from a landmark that may carry extra fields (z, visibility, ...)."""
        return float(point[0]), float(point[1])

    def _shoulder_wrist_slope(self, shoulder, wrist):
        """
        Slope of the line from shoulder to wrist. In a side-on plank
        view this line approximates the straightness of the whole
        body (shoulders/hips/head should all sit close to it), so its
        slope is a useful, landmark-light proxy for overall body
        alignment without needing dedicated hip/head landmarks.
        """
        shoulder_x, shoulder_y = self._xy(shoulder)
        wrist_x, wrist_y = self._xy(wrist)
        dx = wrist_x - shoulder_x
        dy = wrist_y - shoulder_y
        return dy / max(abs(dx), 1e-6)

    def _analyze_posture(self, shoulder, elbow, wrist, angle,
                          just_became_up_stable, just_became_down_stable):
        """
        Run all real-time posture checks for the current frame and
        return the single highest-priority fault message, or None if
        posture looks clean. Purely additive/observational - never
        changes self.stage, self.reps, or the stability counters above.
        """
        # Capture (or refresh) the baseline plank line the first time
        # the arms settle into a stable, fully-extended top position -
        # that's the cleanest moment to trust the user's body is straight.
        if just_became_up_stable or self._plank_baseline_slope is None:
            self._plank_baseline_slope = self._shoulder_wrist_slope(shoulder, wrist)

        current_slope = self._shoulder_wrist_slope(shoulder, wrist)
        baseline_slope = self._plank_baseline_slope
        reference = max(abs(baseline_slope), 0.05)
        deviation = (current_slope - baseline_slope) / reference

        # ---- Straight body / hip position (shared body-line check) ----
        if deviation > self.HIP_SAG_DEVIATION_THRESHOLD:
            # Line steepened well beyond baseline - hips dropping below
            # the shoulder-wrist plank line.
            self._hip_sag_fault_frames += 1
            self._hip_pike_fault_frames = 0
            self._body_misalign_fault_frames = 0
        elif deviation < -self.HIP_PIKE_DEVIATION_THRESHOLD:
            # Line flattened well beyond baseline - hips rising above
            # the shoulder-wrist plank line.
            self._hip_pike_fault_frames += 1
            self._hip_sag_fault_frames = 0
            self._body_misalign_fault_frames = 0
        elif abs(deviation) > self.BODY_MISALIGN_DEVIATION_THRESHOLD:
            # Off the baseline, but not enough to call out a specific
            # hip direction - general body/head alignment drift.
            self._body_misalign_fault_frames += 1
            self._hip_sag_fault_frames = 0
            self._hip_pike_fault_frames = 0
        else:
            self._hip_sag_fault_frames = 0
            self._hip_pike_fault_frames = 0
            self._body_misalign_fault_frames = 0

        # ---- Chest depth: shallow rep that barely crossed DOWN -------
        if (self.stage == "DOWN"
                and angle > self.DOWN_ANGLE_THRESHOLD - self.CHEST_DEPTH_ANGLE_MARGIN):
            self._chest_depth_fault_frames += 1
        else:
            self._chest_depth_fault_frames = 0

        # ---- Elbow extension: arms not fully locked out at the top ---
        if (self.stage == "UP"
                and angle < self.UP_ANGLE_THRESHOLD + self.ELBOW_LOCK_ANGLE_MARGIN):
            self._elbow_lock_fault_frames += 1
        else:
            self._elbow_lock_fault_frames = 0

        # ---- Resolve to the single highest-priority confirmed fault ---
        if self._hip_sag_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Raise Your Hips"
        if self._hip_pike_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Lower Your Hips"
        if self._body_misalign_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Keep Body Straight"
        if self._chest_depth_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Lower More"
        if self._elbow_lock_fault_frames >= self.FAULT_STABLE_FRAMES:
            return "Lock Arms"

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

        if angle < self.DOWN_ANGLE_THRESHOLD:
            # Body is (close to) fully lowered - build up DOWN stability
            # and reset the opposite counter so a single noisy frame
            # can't carry over stability from the other end of the rep.
            self._down_frame_count += 1
            self._up_frame_count = 0

            if self._down_frame_count >= self.REQUIRED_STABLE_FRAMES:
                self.stage = "DOWN"
                self.feedback = "Good Form"
            else:
                self.feedback = "Hold Steady"

        elif angle > self.UP_ANGLE_THRESHOLD:
            # Arms are (close to) fully extended - build up UP stability.
            self._up_frame_count += 1
            self._down_frame_count = 0

            if self._up_frame_count >= self.REQUIRED_STABLE_FRAMES:
                # Only count the rep if:
                #   - the body was previously stable in the DOWN position
                #     (full range of motion, not a half push-up), and
                #   - the cooldown from a previous rep has expired.
                if self.stage == "DOWN" and self._cooldown_frames_remaining == 0:
                    self.stage = "UP"
                    self.reps += 1
                    self._cooldown_frames_remaining = self.REP_COOLDOWN_FRAMES
                    self.feedback = "Excellent Push-up!"
                    rep_counted_this_frame = True
                else:
                    self.stage = "UP"
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
                self.feedback = "Go Lower"
            elif angle < self.MID_RANGE_MIDPOINT:
                self.feedback = "Push Higher"
            else:
                self.feedback = "Straighten Your Arms"

        # ---- POSTURE-ANALYSIS LAYER (additive - does not affect the
        #      rep-counting logic above in any way) ----------------------
        just_became_up_stable = self._up_frame_count == self.REQUIRED_STABLE_FRAMES
        just_became_down_stable = self._down_frame_count == self.REQUIRED_STABLE_FRAMES

        fault_message = self._analyze_posture(
            shoulder, elbow, wrist, angle,
            just_became_up_stable, just_became_down_stable,
        )

        if rep_counted_this_frame:
            # A completed rep is always the most important thing to
            # celebrate - never overridden by a posture note.
            self.feedback = "Excellent Push-up!"
        elif fault_message is not None:
            self.feedback = fault_message
        elif self.feedback == "Good Form":
            # No faults detected and the body is stable at an endpoint -
            # upgrade the generic message to a stronger compliment.
            self.feedback = "Excellent Push-up"
        # Otherwise keep whatever the rep-counting logic already set
        # ("Hold Steady", "Go Lower", "Push Higher", "Straighten Your Arms").

        return {
            "exercise": self.name,
            "angle": round(angle, 2),
            "reps": self.reps,
            "stage": self.stage,
            "feedback": self.feedback
        }