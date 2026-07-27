from core.angle_calculator import AngleCalculator
from workouts.base_workout import BaseWorkout


class ShoulderPressWorkout(BaseWorkout):

    TOP_ANGLE_THRESHOLD = 165
    BOTTOM_ANGLE_THRESHOLD = 90
    MAX_ARM_DIFFERENCE = 20
    MAX_FRAME_JUMP = 35
    STABILITY_FRAMES_REQUIRED = 3
    REP_COOLDOWN_FRAMES = 15

    # --- Full-extension (elbow straightness) heuristic ---
    # Angle must be at least this close to a straight arm (180 deg) at the
    # top of the press before it counts as a fully "straightened" rep.
    FULL_EXTENSION_ANGLE = 172

    # --- Wrist alignment heuristic ---
    # Horizontal offset between wrist and elbow, relative to forearm
    # length (elbow-to-wrist distance). A wrist that drifts too far
    # sideways of the elbow indicates a bent/rolled wrist rather than a
    # neutral, stacked wrist-over-elbow position.
    MAX_WRIST_OFFSET_RATIO = 0.30
    MIN_FOREARM_LENGTH = 1e-3

    # --- Leaning-backward heuristic ---
    # Horizontal drift of the shoulder midpoint (relative to shoulder
    # width) compared to a baseline captured while standing at the
    # bottom/rest position. A large backward drift while pressing
    # indicates the torso is leaning back instead of staying upright.
    MAX_LEAN_SHIFT_RATIO = 0.20
    MIN_SHOULDER_WIDTH = 1e-3

    def __init__(self):
        super().__init__("Shoulder Press")
        self.calculator = AngleCalculator()
        self.stage = "BOTTOM"
        self.reps = 0
        self.feedback = "Get Ready"
        self.angle = 0

        self._top_streak = 0
        self._bottom_streak = 0
        self._last_avg_angle = None
        self._cooldown_counter = 0

        # Baseline shoulder midpoint x, captured while resting at the
        # bottom of the movement, used to detect backward lean.
        self._baseline_shoulder_x = None

    def update(self, left_shoulder, left_elbow, left_wrist,
               right_shoulder, right_elbow, right_wrist):

        landmarks = (left_shoulder, left_elbow, left_wrist,
                     right_shoulder, right_elbow, right_wrist)
        if not self._landmarks_are_valid(landmarks):
            self.feedback = "Balance Your Body"
            return self._build_result(0.0)

        left_angle = self.calculator.calculate(left_shoulder, left_elbow, left_wrist)
        right_angle = self.calculator.calculate(right_shoulder, right_elbow, right_wrist)
        avg_angle = (left_angle + right_angle) / 2
        arm_difference = abs(left_angle - right_angle)

        if self._is_jitter(avg_angle):
            self.feedback = "Hold Steady"
            self._last_avg_angle = avg_angle
            return self._build_result(avg_angle)

        self._last_avg_angle = avg_angle

        if self._cooldown_counter > 0:
            self._cooldown_counter -= 1

        pose = self._classify_pose(avg_angle)
        self._update_streaks(pose)

        # Update the resting-shoulder baseline while stable at the bottom,
        # so later frames have a stable reference point to detect lean.
        if pose == "BOTTOM" and self._bottom_streak >= self.STABILITY_FRAMES_REQUIRED:
            self._baseline_shoulder_x = self._shoulder_midpoint_x(left_shoulder, right_shoulder)

        self._process_stage_transitions(
            pose, avg_angle, arm_difference,
            left_shoulder, left_elbow, left_wrist,
            right_shoulder, right_elbow, right_wrist,
        )

        return self._build_result(avg_angle)

    def _landmarks_are_valid(self, landmarks):
        for point in landmarks:
            if point is None or len(point) != 2:
                return False
            x, y = point
            if x is None or y is None:
                return False
        return True

    def _is_jitter(self, avg_angle):
        if self._last_avg_angle is None:
            return False
        return abs(avg_angle - self._last_avg_angle) > self.MAX_FRAME_JUMP

    def _classify_pose(self, avg_angle):
        if avg_angle > self.TOP_ANGLE_THRESHOLD:
            return "TOP"
        if avg_angle < self.BOTTOM_ANGLE_THRESHOLD:
            return "BOTTOM"
        return "MIDDLE"

    def _update_streaks(self, pose):
        if pose == "TOP":
            self._top_streak += 1
            self._bottom_streak = 0
        elif pose == "BOTTOM":
            self._bottom_streak += 1
            self._top_streak = 0
        else:
            self._top_streak = 0
            self._bottom_streak = 0

    # ------------------------------------------------------------------
    # Posture heuristics
    # ------------------------------------------------------------------

    @staticmethod
    def _distance(point_a, point_b):
        return ((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2) ** 0.5

    @staticmethod
    def _shoulder_midpoint_x(left_shoulder, right_shoulder):
        return (left_shoulder[0] + right_shoulder[0]) / 2

    def _wrist_offset_ratio(self, elbow, wrist):
        """
        Horizontal offset between wrist and elbow, relative to forearm
        length. Large values mean the wrist is not stacked neutrally
        over the elbow (bent/rolled wrist). (Wrist alignment check)
        """
        forearm_length = self._distance(elbow, wrist)
        if forearm_length < self.MIN_FOREARM_LENGTH:
            return 0.0
        offset = abs(wrist[0] - elbow[0])
        return offset / forearm_length

    def _is_wrist_misaligned(self, left_elbow, left_wrist, right_elbow, right_wrist):
        left_ratio = self._wrist_offset_ratio(left_elbow, left_wrist)
        right_ratio = self._wrist_offset_ratio(right_elbow, right_wrist)
        return max(left_ratio, right_ratio) > self.MAX_WRIST_OFFSET_RATIO

    def _is_leaning_back(self, left_shoulder, right_shoulder):
        """
        Compare the current shoulder midpoint x-position to the resting
        baseline captured at the bottom of the movement, relative to
        shoulder width. A large shift indicates the torso has leaned
        backward during the press. (Leaning-backward check)
        """
        if self._baseline_shoulder_x is None:
            return False

        shoulder_width = abs(left_shoulder[0] - right_shoulder[0])
        if shoulder_width < self.MIN_SHOULDER_WIDTH:
            return False

        current_x = self._shoulder_midpoint_x(left_shoulder, right_shoulder)
        shift = abs(current_x - self._baseline_shoulder_x)
        return (shift / shoulder_width) > self.MAX_LEAN_SHIFT_RATIO

    def _process_stage_transitions(
        self, pose, avg_angle, arm_difference,
        left_shoulder, left_elbow, left_wrist,
        right_shoulder, right_elbow, right_wrist,
    ):

        if arm_difference > self.MAX_ARM_DIFFERENCE:
            self.feedback = "Press Both Arms Together"
            return

        if self._is_leaning_back(left_shoulder, right_shoulder):
            self.feedback = "Avoid Leaning Back"
            return

        if self.stage == "BOTTOM" and pose == "TOP":
            if self._top_streak >= self.STABILITY_FRAMES_REQUIRED:

                if self._is_wrist_misaligned(left_elbow, left_wrist, right_elbow, right_wrist):
                    self.feedback = "Keep Wrists Neutral"
                    return

                if avg_angle < self.FULL_EXTENSION_ANGLE:
                    self.feedback = "Straighten Arms"
                    return

                self.stage = "TOP"

                if self._cooldown_counter == 0:
                    self.reps += 1
                    self._cooldown_counter = self.REP_COOLDOWN_FRAMES
                    self.feedback = "Excellent Press"
                else:
                    self.feedback = "Excellent Press"
            return

        if self.stage == "TOP" and pose == "BOTTOM":
            if self._bottom_streak >= self.STABILITY_FRAMES_REQUIRED:
                self.stage = "BOTTOM"
                self.feedback = "Lower Your Arms"
            return

        if self.stage == "BOTTOM" and pose == "MIDDLE":
            self.feedback = "Press Higher"
            return

        if self.stage == "TOP" and pose == "MIDDLE":
            self.feedback = "Straighten Arms"
            return

        if pose == "TOP":
            if self._is_wrist_misaligned(left_elbow, left_wrist, right_elbow, right_wrist):
                self.feedback = "Keep Wrists Neutral"
            elif avg_angle < self.FULL_EXTENSION_ANGLE:
                self.feedback = "Straighten Arms"
            else:
                self.feedback = "Excellent Press"
        elif pose == "BOTTOM":
            self.feedback = "Press Higher"
        else:
            self.feedback = "Press Higher"

    def _build_result(self, avg_angle):
        return {
            "exercise": self.name,
            "angle": round(avg_angle, 1),
            "reps": self.reps,
            "stage": self.stage,
            "feedback": self.feedback,
        }