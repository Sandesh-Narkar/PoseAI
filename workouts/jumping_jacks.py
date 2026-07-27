"""
workouts/jumping_jacks.py
--------------------------
Jumping Jacks workout logic.

Robust, jitter-resistant, fast-motion-tolerant jumping jack detector built
on top of the existing BaseWorkout/AngleCalculator architecture.

The public update() signature is unchanged:
update(self, left_shoulder, right_shoulder, left_hip, right_hip,
       left_wrist, right_wrist, left_ankle, right_ankle)

A repetition is only counted when a FULL, SYNCHRONIZED cycle is observed:

    READY (arms down + feet together)
        -> OPEN  (arms overhead + feet apart)
        -> READY (arms down + feet together)

Arm-only or leg-only movement never triggers a stage change or a rep.
Posture analysis additionally checks arm height, leg width, timing
(how quickly a signal reaches its extreme) and synchronization (how
closely the arm and leg extremes line up with each other), to give
more targeted coaching feedback.
"""

import math
from collections import deque

from workouts.base_workout import BaseWorkout
from core.angle_calculator import AngleCalculator


class JumpingJacksWorkout(BaseWorkout):
    """
    update() args: (left_shoulder, right_shoulder, left_hip, right_hip,
                     left_wrist, right_wrist, left_ankle, right_ankle)
    8 positional args, exactly this order. All args are (x, y) tuples.
    """

    # --- Arm angle thresholds (degrees), measured hip-shoulder-wrist ---
    ARMS_UP_ANGLE = 140         # above this => arms considered raised overhead
    ARMS_DOWN_ANGLE = 40        # below this => arms considered lowered

    # --- Wrist / shoulder vertical relationship (adaptive, scale-free) ---
    # Positive margin (normalized by shoulder width) required for the wrist
    # to be considered clearly above/below the shoulder line. This lets us
    # confirm "arms up"/"arms down" using a second independent signal
    # instead of relying on angle alone.
    WRIST_HEIGHT_MARGIN_RATIO = 0.05

    # --- Leg spread thresholds (ankle distance / shoulder distance ratio) ---
    LEGS_APART_RATIO = 1.5      # above this => feet considered apart
    LEGS_TOGETHER_RATIO = 1.15  # below this => feet considered together

    # --- Motion smoothing (exponential moving average) ---
    # Instead of hard-rejecting large frame-to-frame deltas (which would
    # discard *legitimate* fast jumping-jack motion), we smooth the raw
    # signals with an EMA. This damps single-frame MediaPipe jitter while
    # still tracking fast, real movement quickly.
    EMA_ALPHA = 0.55

    # --- Stability / debounce settings ---
    # Kept low so quick jumping jacks are not missed, while still filtering
    # single-frame noise.
    STABILITY_FRAMES_REQUIRED = 2

    # --- Cooldown after a counted rep (frames) ---
    # Short cooldown: the READY->OPEN->READY state machine is itself the
    # primary double-count guard, this just absorbs threshold-edge noise
    # right at the moment of the transition.
    REP_COOLDOWN_FRAMES = 4

    # --- Rhythm feedback ---
    FAST_REP_FRAME_THRESHOLD = 30   # frames between reps considered "fast"
    STALL_FRAMES_THRESHOLD = 90     # frames stuck without completing a rep

    # --- Synchronization / timing heuristic ---
    # Max allowed gap (in frames) between the arms and legs each first
    # reaching their own individual extreme (up/apart) while moving toward
    # OPEN. A large gap means the movement wasn't performed together.
    MAX_SYNC_GAP_FRAMES = 8

    def __init__(self):
        super().__init__("Jumping Jacks")
        self.calculator = AngleCalculator()

        # Default to a known, safe starting stage.
        self.stage = "READY"
        self.feedback = "Good Form"

        # Internal stability tracking (not part of the public output contract).
        self._open_streak = 0
        self._ready_streak = 0

        # Smoothed (EMA) signal values, used for thresholding instead of
        # raw per-frame values to reject MediaPipe jitter.
        self._smoothed_arm_angle = None
        self._smoothed_leg_ratio = None

        # Frame-based cooldown to prevent double-counting a single rep.
        self._cooldown_counter = 0

        # Rhythm / stall tracking for richer feedback.
        self._frames_since_last_rep = 0
        self._frames_in_current_stage = 0

        # Timing / synchronization tracking: frame index (relative to the
        # start of the current READY->OPEN attempt) at which arms and legs
        # each first individually reached their extreme.
        self._frames_since_ready = 0
        self._arms_up_first_frame = None
        self._legs_apart_first_frame = None

    def update(self, left_shoulder, right_shoulder,
               left_hip, right_hip,
               left_wrist, right_wrist,
               left_ankle, right_ankle):

        # --- 1. Validate landmark tracking quality ---
        landmarks = (left_shoulder, right_shoulder, left_hip, right_hip,
                     left_wrist, right_wrist, left_ankle, right_ankle)
        if not self._landmarks_are_valid(landmarks):
            self.feedback = "Balance Your Body"
            return self._build_result(0.0, 0.0)

        # --- 2. Compute raw arm angle (average of both arms) ---
        left_arm_angle = self.calculator.calculate(left_hip, left_shoulder, left_wrist)
        right_arm_angle = self.calculator.calculate(right_hip, right_shoulder, right_wrist)
        raw_arm_angle = (left_arm_angle + right_arm_angle) / 2

        # --- 3. Compute raw leg spread ratio (scale-invariant via shoulder width) ---
        shoulder_dist = math.dist(left_shoulder, right_shoulder)
        ankle_dist = math.dist(left_ankle, right_ankle)
        raw_leg_ratio = ankle_dist / shoulder_dist if shoulder_dist > 0 else 0.0

        # --- 4. Smooth signals (EMA) to damp jitter without discarding fast motion ---
        arm_angle = self._smooth_arm_angle(raw_arm_angle)
        leg_spread_ratio = self._smooth_leg_ratio(raw_leg_ratio)

        # --- 5. Tick down the rep cooldown / rhythm counters ---
        if self._cooldown_counter > 0:
            self._cooldown_counter -= 1
        self._frames_since_last_rep += 1
        self._frames_in_current_stage += 1
        self._frames_since_ready += 1

        # --- 6. Adaptive multi-signal classification of body parts ---
        arms_up, arms_down = self._classify_arms(
            arm_angle, left_shoulder, right_shoulder, left_wrist, right_wrist, shoulder_dist
        )
        legs_apart = leg_spread_ratio > self.LEGS_APART_RATIO
        legs_together = leg_spread_ratio < self.LEGS_TOGETHER_RATIO

        # --- 7. Track timing: first frame each signal reaches its extreme ---
        self._track_extreme_timing(arms_up, legs_apart)

        # --- 8. Classify the full-body synchronized pose ---
        pose = self._classify_pose(arms_up, arms_down, legs_apart, legs_together)

        # --- 9. Update stability streaks (hysteresis / debounce) ---
        self._update_streaks(pose)

        # --- 10. Stage transition state machine ---
        self._process_stage_transitions(pose, arms_up, arms_down, legs_apart, legs_together)

        return self._build_result(arm_angle, leg_spread_ratio)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _landmarks_are_valid(self, landmarks):
        """Basic sanity check that all required points were tracked properly."""
        for point in landmarks:
            if point is None or len(point) != 2:
                return False
            x, y = point
            if x is None or y is None or math.isnan(x) or math.isnan(y):
                return False
        return True

    def _smooth_arm_angle(self, raw_value):
        """Exponentially smooth the arm angle signal to reduce jitter."""
        if self._smoothed_arm_angle is None:
            self._smoothed_arm_angle = raw_value
        else:
            self._smoothed_arm_angle = (
                self.EMA_ALPHA * raw_value + (1 - self.EMA_ALPHA) * self._smoothed_arm_angle
            )
        return self._smoothed_arm_angle

    def _smooth_leg_ratio(self, raw_value):
        """Exponentially smooth the leg spread ratio signal to reduce jitter."""
        if self._smoothed_leg_ratio is None:
            self._smoothed_leg_ratio = raw_value
        else:
            self._smoothed_leg_ratio = (
                self.EMA_ALPHA * raw_value + (1 - self.EMA_ALPHA) * self._smoothed_leg_ratio
            )
        return self._smoothed_leg_ratio

    def _classify_arms(self, arm_angle, left_shoulder, right_shoulder,
                        left_wrist, right_wrist, shoulder_dist):
        """
        Adaptive arms classification combining arm angle with wrist/shoulder
        vertical relationship, normalized by shoulder width so it works at
        any distance from the camera. (Arm height check)
        """
        if shoulder_dist <= 0:
            return False, False

        margin = shoulder_dist * self.WRIST_HEIGHT_MARGIN_RATIO

        # Note: image coordinates -> smaller y is higher on screen.
        avg_shoulder_y = (left_shoulder[1] + right_shoulder[1]) / 2
        avg_wrist_y = (left_wrist[1] + right_wrist[1]) / 2

        wrists_above_shoulders = avg_wrist_y < (avg_shoulder_y - margin)
        wrists_at_or_below_shoulders = avg_wrist_y > (avg_shoulder_y + margin)

        arms_up = (arm_angle > self.ARMS_UP_ANGLE) and wrists_above_shoulders
        arms_down = (arm_angle < self.ARMS_DOWN_ANGLE) and wrists_at_or_below_shoulders

        return arms_up, arms_down

    def _track_extreme_timing(self, arms_up, legs_apart):
        """
        Record the frame (relative to entering READY) at which arms and
        legs each first individually reach their "open" extreme, so the
        gap between them can be used as a synchronization / timing signal.
        Reset once both have been captured for the current attempt or once
        back in READY with everything down/together.
        """
        if self.stage == "READY":
            if arms_up and self._arms_up_first_frame is None:
                self._arms_up_first_frame = self._frames_since_ready
            if legs_apart and self._legs_apart_first_frame is None:
                self._legs_apart_first_frame = self._frames_since_ready

    def _reset_timing_tracking(self):
        """Reset per-attempt timing trackers at the start of a new cycle."""
        self._frames_since_ready = 0
        self._arms_up_first_frame = None
        self._legs_apart_first_frame = None

    def _sync_gap_frames(self):
        """
        Frame gap between arms and legs each first reaching their extreme
        during the current attempt, or None if either hasn't reached it yet.
        """
        if self._arms_up_first_frame is None or self._legs_apart_first_frame is None:
            return None
        return abs(self._arms_up_first_frame - self._legs_apart_first_frame)

    def _classify_pose(self, arms_up, arms_down, legs_apart, legs_together):
        """
        Classify the current frame as a full-body synchronized OPEN or
        READY (closed) pose. Anything else (including arm-only or leg-only
        movement) is a PARTIAL pose and never drives a stage change.
        """
        if arms_up and legs_apart:
            return "OPEN"
        if arms_down and legs_together:
            return "READY"
        return "PARTIAL"

    def _update_streaks(self, pose):
        """Maintain consecutive-frame counters used to debounce stage changes."""
        if pose == "OPEN":
            self._open_streak += 1
            self._ready_streak = 0
        elif pose == "READY":
            self._ready_streak += 1
            self._open_streak = 0
        else:
            # Partial / unsynchronized movement resets both streaks so a
            # brief, noisy oscillation never accumulates toward a change.
            self._open_streak = 0
            self._ready_streak = 0

    def _process_stage_transitions(self, pose, arms_up, arms_down, legs_apart, legs_together):
        """Core READY -> OPEN -> READY state machine with cooldown."""

        # READY -> OPEN
        if self.stage == "READY" and pose == "OPEN":
            if self._open_streak >= self.STABILITY_FRAMES_REQUIRED:
                sync_gap = self._sync_gap_frames()

                if sync_gap is not None and sync_gap > self.MAX_SYNC_GAP_FRAMES:
                    # Arms and legs individually reached the "open" extreme,
                    # but too far apart in time to count as one clean rep.
                    self.feedback = "Synchronize Arms and Legs"
                    self.stage = "OPEN"
                    self._frames_in_current_stage = 0
                    return

                self.stage = "OPEN"
                self.feedback = "Excellent Rep"
                self._frames_in_current_stage = 0
            return

        # OPEN -> READY (closes out a rep, subject to cooldown)
        if self.stage == "OPEN" and pose == "READY":
            if self._ready_streak >= self.STABILITY_FRAMES_REQUIRED:
                self.stage = "READY"
                self._frames_in_current_stage = 0
                self._reset_timing_tracking()

                if self._cooldown_counter == 0:
                    self.reps += 1
                    self._cooldown_counter = self.REP_COOLDOWN_FRAMES
                    self.feedback = "Excellent Rep"
                    self._frames_since_last_rep = 0
                else:
                    self.feedback = "Good Form"
            return

        # Partial / unsynchronized movement while in READY: guide the user.
        if self.stage == "READY" and pose == "PARTIAL":
            self.feedback = self._partial_feedback(arms_up, arms_down, legs_apart, legs_together)
            return

        # Partial / unsynchronized movement while OPEN: guide the user back.
        if self.stage == "OPEN" and pose == "PARTIAL":
            self.feedback = self._partial_feedback(arms_up, arms_down, legs_apart, legs_together)
            return

        # Holding steady in a recognized, synchronized position.
        if pose == "OPEN":
            if self._frames_in_current_stage > self.STALL_FRAMES_THRESHOLD:
                self.feedback = "Move Faster"
            else:
                self.feedback = "Excellent Rep"
        elif pose == "READY":
            self.feedback = "Good Form"

    def _partial_feedback(self, arms_up, arms_down, legs_apart, legs_together):
        """
        Give targeted guidance when arms and legs are out of sync, checking
        arm height, leg width, and overall synchronization/timing.
        """
        arms_ready = arms_up or arms_down
        legs_ready = legs_apart or legs_together

        if not arms_ready and legs_ready:
            return "Raise Arms Higher" if not arms_up else "Synchronize Arms and Legs"
        if arms_ready and not legs_ready:
            return "Jump Wider" if not legs_apart else "Synchronize Arms and Legs"
        if not arms_ready and not legs_ready:
            return "Synchronize Arms and Legs"

        # Both parts individually reached a recognizable extreme, but not
        # the same one at the same time (e.g. arms up while legs together),
        # or reached them too far apart in time (timing/sync check).
        return "Synchronize Arms and Legs"

    def _build_result(self, arm_angle, leg_spread_ratio):
        """Assemble the output contract expected by the rest of the app."""
        return {
            "exercise": self.name,
            "angle": round(arm_angle, 1),
            "leg_spread_ratio": round(leg_spread_ratio, 2),
            "reps": self.reps,
            "stage": self.stage,
            "feedback": self.feedback,
        }