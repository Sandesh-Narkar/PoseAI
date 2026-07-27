"""
burpees.py
-----------
Burpees workout tracker.

Enforces the full burpee sequence, in strict order, before a single
repetition is counted:

    STANDING -> SQUAT -> PLANK -> RETURN (back to squat) -> STANDING

If the user skips a stage (e.g. stands up early, or jumps straight
from standing to plank), the sequence resets and no rep is counted
until the entire cycle is performed again, cleanly, in order.

NOTE: Pose classification (especially PLANK) is tuned to work from a
FRONT-FACING camera. It relies on joint angles (knee, hip-fold, and
shoulder-hip-ankle body-line) rather than raw y-coordinate comparisons,
since a front camera doesn't show the body going "horizontal" in the
same way a side camera would.

POSTURE ANALYSIS:
Because the fixed update() signature only provides shoulder/hip/knee/
ankle landmarks (no wrist/elbow), the following checks are approximated
from those points alone:

    * Squat depth   - avg knee angle must reach a strict depth
                       threshold before the SQUAT stage is accepted.
    * Push-up phase - shoulder-to-hip vertical distance (normalized by
                       torso/body-line length) must dip enough while in
                       PLANK, approximating the chest lowering on the
                       down-phase of a push-up, before RETURN is accepted.
    * Jump height   - hip vertical rise during the RETURN -> STANDING
                       transition, normalized by leg length, must clear
                       a minimum threshold to count as a real jump.
    * Landing       - frame-to-frame hip vertical velocity right as the
                       STANDING pose stabilizes must stay under a soft
                       threshold, flagging hard/bouncy landings.
"""

from core.angle_calculator import AngleCalculator
from workouts.base_workout import BaseWorkout


class BurpeesWorkout(BaseWorkout):

    STAGE_SEQUENCE = ["STANDING", "SQUAT", "PLANK", "RETURN", "STANDING"]

    RAW_POSE_FOR_STAGE = {
        "STANDING": "STANDING",
        "SQUAT": "SQUAT",
        "PLANK": "PLANK",
        "RETURN": "SQUAT",
    }

    # --- Angle thresholds (degrees) ---
    STANDING_KNEE_ANGLE = 155
    STANDING_HIP_ANGLE = 155
    SQUAT_KNEE_ANGLE = 110
    SQUAT_HIP_ANGLE = 110

    # Stricter depth requirement (on top of SQUAT_KNEE_ANGLE classification)
    # that must be reached before a SQUAT is accepted as "deep enough" to
    # progress the sequence. (Squat depth check)
    SQUAT_DEPTH_ANGLE = 100

    # Plank, from a FRONT camera: knees stay relatively extended, and
    # the shoulder-hip-ankle body-line angle stays close to straight
    # (near 180) even though the whole body appears compressed/foreshortened
    # in the frame - it's the angle, not the raw y-position, that stays
    # reliable from the front.
    PLANK_KNEE_ANGLE = 140
    PLANK_BODY_LINE_MIN = 150
    PLANK_BODY_LINE_MAX = 180
    # Torso "fold" angle (shoulder-hip-knee) also stays open/near-straight
    # in a plank, unlike a squat where it's sharply folded.
    PLANK_HIP_FOLD_MIN = 150

    # Minimum drop in the shoulder-to-hip vertical distance (relative to
    # the shoulder-hip-ankle body-line length) required while in PLANK to
    # count as a genuine push-up down-phase. (Push-up phase check)
    PUSHUP_DIP_RATIO = 0.08

    # --- Jump height heuristic ---
    # Minimum upward hip travel (squat hip_y - lowest hip_y reached while
    # airborne) relative to leg length, required to count as a real jump
    # rather than a slow stand-up. (Jump height check)
    JUMP_HEIGHT_RATIO_MIN = 0.12

    # --- Landing control heuristic ---
    # Maximum allowed frame-to-frame hip vertical velocity (relative to
    # leg length) right as STANDING becomes stable again. Larger values
    # indicate a hard, uncontrolled/bouncy landing. (Landing check)
    MAX_LANDING_VELOCITY_RATIO = 0.05

    MIN_REF_LENGTH = 1e-3

    # --- Anti camera-shake: reject implausible frame-to-frame jumps ---
    MAX_ANGLE_JUMP = 40

    # --- Stability / debounce settings ---
    STABILITY_FRAMES_REQUIRED = 2

    # --- Cooldown after a counted rep ---
    REP_COOLDOWN_FRAMES = 20

    def __init__(self):
        super().__init__("Burpees")
        self.calculator = AngleCalculator()

        self.stage = "STANDING"
        self.reps = 0
        self.feedback = "Get Ready"
        self.angle = 0

        self._sequence_index = 0
        self._pose_streaks = {"STANDING": 0, "SQUAT": 0, "PLANK": 0}

        self._last_knee_angle = None
        self._last_hip_angle = None

        self._cooldown_counter = 0

        # --- Posture-analysis tracking state ---
        # Push-up phase: minimum shoulder-hip / body-line ratio seen while
        # currently in the PLANK stage (reset whenever PLANK is (re)entered).
        self._plank_min_dip_ratio = None
        self._pushup_dip_confirmed = False

        # Jump height: hip_y baseline captured at the bottom of the squat,
        # and the lowest hip_y (i.e. highest point in the air, since smaller
        # y = higher on screen) observed since leaving the squat.
        self._squat_hip_y = None
        self._airborne_min_hip_y = None
        self._leg_length_ref = None

        # Landing control: previous frame's hip_y, used to compute vertical
        # velocity right as STANDING stabilizes again.
        self._prev_hip_y = None

    def _leg_angle(self, hip, knee, ankle):
        return self.calculator.calculate(hip, knee, ankle)

    def _torso_angle(self, shoulder, hip, knee):
        return self.calculator.calculate(shoulder, hip, knee)

    def _body_line_angle(self, shoulder, hip, ankle):
        return self.calculator.calculate(shoulder, hip, ankle)

    @staticmethod
    def _distance(point_a, point_b):
        return ((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2) ** 0.5

    def update(self, left_shoulder, left_hip, left_knee, left_ankle,
               right_shoulder, right_hip, right_knee, right_ankle):

        landmarks = (left_shoulder, left_hip, left_knee, left_ankle,
                     right_shoulder, right_hip, right_knee, right_ankle)
        if not self._landmarks_are_valid(landmarks):
            self.feedback = "Balance Your Body"
            return self._build_result(0.0)

        avg_knee_angle = (
            self._leg_angle(left_hip, left_knee, left_ankle)
            + self._leg_angle(right_hip, right_knee, right_ankle)
        ) / 2

        avg_hip_angle = (
            self._torso_angle(left_shoulder, left_hip, left_knee)
            + self._torso_angle(right_shoulder, right_hip, right_knee)
        ) / 2

        avg_body_line_angle = (
            self._body_line_angle(left_shoulder, left_hip, left_ankle)
            + self._body_line_angle(right_shoulder, right_hip, right_ankle)
        ) / 2

        avg_shoulder_hip_dist = (
            self._distance(left_shoulder, left_hip) + self._distance(right_shoulder, right_hip)
        ) / 2
        avg_body_line_length = (
            self._distance(left_shoulder, left_ankle) + self._distance(right_shoulder, right_ankle)
        ) / 2
        avg_leg_length = (
            self._distance(left_hip, left_knee) + self._distance(left_knee, left_ankle)
            + self._distance(right_hip, right_knee) + self._distance(right_knee, right_ankle)
        ) / 2
        avg_hip_y = (left_hip[1] + right_hip[1]) / 2

        self.angle = avg_knee_angle

        if self._is_jitter(avg_knee_angle, avg_hip_angle):
            self.feedback = "Hold Steady"
            self._last_knee_angle = avg_knee_angle
            self._last_hip_angle = avg_hip_angle
            self._prev_hip_y = avg_hip_y
            return self._build_result(avg_knee_angle)

        self._last_knee_angle = avg_knee_angle
        self._last_hip_angle = avg_hip_angle

        if self._cooldown_counter > 0:
            self._cooldown_counter -= 1

        raw_pose = self._classify_pose(avg_knee_angle, avg_hip_angle, avg_body_line_angle)

        self._update_streaks(raw_pose)

        # --- Track push-up dip while physically in the PLANK stage ---
        if self.stage == "PLANK" and avg_body_line_length > self.MIN_REF_LENGTH:
            dip_ratio = avg_shoulder_hip_dist / avg_body_line_length
            if self._plank_min_dip_ratio is None or dip_ratio < self._plank_min_dip_ratio:
                self._plank_min_dip_ratio = dip_ratio

        # --- Track jump apex while past the squat, airborne toward standing ---
        if self.stage in ("PLANK", "RETURN") and self._squat_hip_y is not None:
            if self._airborne_min_hip_y is None or avg_hip_y < self._airborne_min_hip_y:
                self._airborne_min_hip_y = avg_hip_y

        self._process_sequence(raw_pose, avg_body_line_angle, avg_knee_angle,
                                avg_hip_y, avg_leg_length)

        self._prev_hip_y = avg_hip_y

        return self._build_result(avg_knee_angle)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _landmarks_are_valid(self, landmarks):
        for point in landmarks:
            if point is None or len(point) != 2:
                return False
            x, y = point
            if x is None or y is None:
                return False
        return True

    def _is_jitter(self, avg_knee_angle, avg_hip_angle):
        if self._last_knee_angle is None or self._last_hip_angle is None:
            return False
        knee_jumped = abs(avg_knee_angle - self._last_knee_angle) > self.MAX_ANGLE_JUMP
        hip_jumped = abs(avg_hip_angle - self._last_hip_angle) > self.MAX_ANGLE_JUMP
        return knee_jumped or hip_jumped

    def _classify_pose(self, avg_knee_angle, avg_hip_angle, avg_body_line_angle):
        """
        Classify the current frame as STANDING, SQUAT, PLANK, or UNKNOWN,
        using only joint angles (front-camera safe - no reliance on raw
        y-coordinate "horizontal body" checks).
        """
        # PLANK checked first: legs relatively extended, hip fold open,
        # AND body-line angle straight - this combination is distinct
        # from standing (where hip fold is much closer to 180 too, but
        # body-line is vertical/near-180 in a different orientation) and
        # from squat (where knee and hip-fold are both sharply bent).
        if (
            avg_knee_angle > self.PLANK_KNEE_ANGLE
            and avg_hip_angle > self.PLANK_HIP_FOLD_MIN
            and self.PLANK_BODY_LINE_MIN <= avg_body_line_angle <= self.PLANK_BODY_LINE_MAX
            and avg_knee_angle <= self.STANDING_KNEE_ANGLE
        ):
            return "PLANK"

        if avg_knee_angle > self.STANDING_KNEE_ANGLE and avg_hip_angle > self.STANDING_HIP_ANGLE:
            return "STANDING"

        if avg_knee_angle < self.SQUAT_KNEE_ANGLE and avg_hip_angle < self.SQUAT_HIP_ANGLE:
            return "SQUAT"

        return "UNKNOWN"

    def _update_streaks(self, raw_pose):
        for pose_name in self._pose_streaks:
            if pose_name == raw_pose:
                self._pose_streaks[pose_name] += 1
            else:
                self._pose_streaks[pose_name] = 0

    def _is_pose_stable(self, raw_pose):
        return self._pose_streaks.get(raw_pose, 0) >= self.STABILITY_FRAMES_REQUIRED

    def _reset_rep_tracking(self):
        """Reset all posture-analysis trackers for a fresh attempt."""
        self._plank_min_dip_ratio = None
        self._pushup_dip_confirmed = False
        self._squat_hip_y = None
        self._airborne_min_hip_y = None

    def _process_sequence(self, raw_pose, avg_body_line_angle, avg_knee_angle,
                           avg_hip_y, avg_leg_length):
        expected_stage = self.STAGE_SEQUENCE[self._sequence_index + 1]
        expected_raw_pose = self.RAW_POSE_FOR_STAGE[expected_stage]

        if raw_pose == expected_raw_pose and self._is_pose_stable(raw_pose):

            # --- Gate: SQUAT stage requires sufficient depth ---
            if expected_stage == "SQUAT" and self._sequence_index == 0:
                if avg_knee_angle > self.SQUAT_DEPTH_ANGLE:
                    self.feedback = "Lower More"
                    return
                self._squat_hip_y = avg_hip_y
                self._airborne_min_hip_y = avg_hip_y

            # --- Gate: RETURN requires a confirmed push-up dip in PLANK ---
            if expected_stage == "RETURN":
                if not self._pushup_dip_confirmed:
                    self.feedback = "Lower More"
                    return

            self._sequence_index += 1
            self.stage = expected_stage

            if expected_stage == "STANDING" and self._sequence_index == len(self.STAGE_SEQUENCE) - 1:
                # --- Gate/feedback: jump height + landing control ---
                jump_issue = self._check_jump_height(avg_hip_y, avg_leg_length)
                landing_issue = self._check_landing_control(avg_hip_y, avg_leg_length)

                if jump_issue:
                    self.feedback = "Jump Higher"
                elif landing_issue:
                    self.feedback = "Control Landing"
                elif self._cooldown_counter == 0:
                    self.reps += 1
                    self._cooldown_counter = self.REP_COOLDOWN_FRAMES
                    self.feedback = "Excellent Burpee"
                else:
                    self.feedback = "Excellent Burpee"

                self._sequence_index = 0
                self._reset_rep_tracking()
            elif expected_stage == "SQUAT":
                self.feedback = "Good Squat"
            elif expected_stage == "PLANK":
                self._plank_min_dip_ratio = None
                self._pushup_dip_confirmed = False
                self.feedback = "Perfect Form"
            elif expected_stage == "RETURN":
                self.feedback = "Good Form"
            return

        # --- While physically in PLANK, confirm the push-up dip as soon
        #     as it happens, independent of the SQUAT/RETURN transition
        #     check above (so it's captured even a few frames early).
        if self.stage == "PLANK" and not self._pushup_dip_confirmed:
            if self._plank_min_dip_ratio is not None:
                # A drop from the initial (near body-line-length) ratio of
                # roughly 1.0 down past PUSHUP_DIP_RATIO below that counts
                # as a genuine chest-lowering push-up phase.
                if self._plank_min_dip_ratio <= (1.0 - self.PUSHUP_DIP_RATIO):
                    self._pushup_dip_confirmed = True

        if raw_pose == "STANDING" and self._is_pose_stable(raw_pose) and self._sequence_index != 0:
            self._sequence_index = 0
            self.stage = "STANDING"
            self.feedback = "Stand Up Completely"
            self._reset_rep_tracking()
            return

        if raw_pose == "UNKNOWN" and expected_stage == "PLANK":
            if avg_body_line_angle < self.PLANK_BODY_LINE_MIN:
                self.feedback = "Keep Your Back Straight"
            else:
                self.feedback = "Move Into Plank"
            return

        if expected_stage == "SQUAT":
            self.feedback = "Lower More" if self._sequence_index == 0 else "Return to Squat"
        elif expected_stage == "PLANK":
            self.feedback = "Move Into Plank"
        elif expected_stage == "RETURN":
            self.feedback = "Return to Squat"
        elif expected_stage == "STANDING":
            self.feedback = "Stand Up Completely"

    def _check_jump_height(self, avg_hip_y, avg_leg_length):
        """
        Compare how high the hips rose (smallest hip_y reached while
        airborne) against the squat baseline, normalized by leg length.
        Returns True if the jump was too shallow. (Jump height check)
        """
        if self._squat_hip_y is None or self._airborne_min_hip_y is None:
            return False
        if avg_leg_length < self.MIN_REF_LENGTH:
            return False

        rise = self._squat_hip_y - self._airborne_min_hip_y
        rise_ratio = rise / avg_leg_length
        return rise_ratio < self.JUMP_HEIGHT_RATIO_MIN

    def _check_landing_control(self, avg_hip_y, avg_leg_length):
        """
        Check the hip's frame-to-frame vertical velocity right as
        STANDING stabilizes again. A large spike suggests a hard,
        uncontrolled landing rather than a soft, controlled one.
        (Landing check)
        """
        if self._prev_hip_y is None or avg_leg_length < self.MIN_REF_LENGTH:
            return False

        velocity = abs(avg_hip_y - self._prev_hip_y)
        velocity_ratio = velocity / avg_leg_length
        return velocity_ratio > self.MAX_LANDING_VELOCITY_RATIO

    def _build_result(self, avg_knee_angle):
        return {
            "exercise": self.name,
            "angle": round(avg_knee_angle, 1),
            "reps": self.reps,
            "stage": self.stage,
            "feedback": self.feedback,
        }