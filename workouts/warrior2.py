import math
import time

from core.angle_calculator import AngleCalculator
from workouts.base_workout import BaseWorkout


class Warrior2Workout(BaseWorkout):
    """
    Warrior II (Virabhadrasana II) pose hold tracker.

    Front knee should bend to 80 deg-110 deg, back leg should stay
    straight at 165 deg-180 deg. While the pose is held correctly, a
    timer accumulates hold_time. Stage is "HOLD" while correct,
    otherwise it reports the correction needed.

    POSTURE ANALYSIS NOTE:
    The public update() signature is fixed by the rest of the project
    as update(self, front_hip, front_knee, front_ankle, back_hip,
    back_knee, back_ankle) - only leg landmarks for the front and back
    leg are provided (no shoulder/wrist/head landmarks). To still
    surface arm-level, torso-vertical, and head-direction feedback
    without changing that signature, those three checks are
    approximated from the six leg landmarks already available:

        * Arm level      - in a correct Warrior II, the arms are held
                            out parallel to the shoulder/hip line. The
                            hip line (front_hip -> back_hip) is used as
                            a stand-in: if it isn't roughly level, the
                            upper body (and therefore the arms) isn't
                            held level either.
        * Torso vertical  - approximated by how centered the hip
                            midpoint is over the midpoint of the two
                            feet (front_ankle / back_ankle). A torso
                            leaning off to one side pulls the hips away
                            from that centered base.
        * Head direction  - approximated by how well the front knee
                            tracks over the front ankle. Looking
                            forward over the front leg naturally keeps
                            the body's forward-facing alignment intact;
                            a front knee that drifts far from the
                            ankle line suggests the body (and gaze)
                            has turned away from the forward direction.

    These are heuristic geometric proxies for coaching purposes, not a
    biomechanical measurement of the arms or head themselves.
    """

    FRONT_KNEE_MIN = 80
    FRONT_KNEE_MAX = 110
    BACK_KNEE_MIN = 165
    BACK_KNEE_MAX = 180

    # --- Arm-level heuristic (via hip line) ---
    # Vertical difference between front_hip and back_hip, relative to
    # the horizontal hip separation, beyond which the hip/shoulder
    # line (and therefore the arms) is considered uneven.
    MAX_HIP_LINE_TILT_RATIO = 0.20

    # --- Torso-vertical heuristic (hip centered over stance) ---
    # Horizontal offset of the hip midpoint from the midpoint of the
    # two feet, relative to stance width, beyond which the torso is
    # considered to be leaning off-center.
    MAX_TORSO_OFFSET_RATIO = 0.30

    # --- Head-direction heuristic (front knee over front ankle) ---
    # Horizontal offset between front_knee and front_ankle, relative
    # to front leg length, beyond which the body/gaze is considered
    # to have turned away from facing forward.
    MAX_HEAD_DRIFT_RATIO = 0.35

    MIN_REF_LENGTH = 1e-3

    def __init__(self):
        super().__init__("Warrior II")
        self.calculator = AngleCalculator()
        self.stage = "IDLE"
        self.hold_time = 0.0
        self.feedback = "Get Into Position"
        self.front_angle = 0
        self.back_angle = 0
        self._hold_start_time = None

    @staticmethod
    def _distance(point_a, point_b):
        return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])

    def _arm_level_ok(self, front_hip, back_hip):
        """Proxy 'arm level' check via the front-to-back hip line tilt."""
        hip_span = abs(front_hip[0] - back_hip[0])
        if hip_span < self.MIN_REF_LENGTH:
            return True
        tilt_ratio = abs(front_hip[1] - back_hip[1]) / hip_span
        return tilt_ratio <= self.MAX_HIP_LINE_TILT_RATIO

    def _torso_vertical_ok(self, front_hip, back_hip, front_ankle, back_ankle):
        """Proxy 'torso vertical' check via hip midpoint centered over stance."""
        stance_width = abs(front_ankle[0] - back_ankle[0])
        if stance_width < self.MIN_REF_LENGTH:
            return True
        hip_mid_x = (front_hip[0] + back_hip[0]) / 2
        stance_mid_x = (front_ankle[0] + back_ankle[0]) / 2
        offset_ratio = abs(hip_mid_x - stance_mid_x) / stance_width
        return offset_ratio <= self.MAX_TORSO_OFFSET_RATIO

    def _head_direction_ok(self, front_knee, front_ankle, front_hip):
        """Proxy 'head direction' check via front knee tracking over front ankle."""
        leg_length = self._distance(front_hip, front_knee) + self._distance(front_knee, front_ankle)
        if leg_length < self.MIN_REF_LENGTH:
            return True
        drift_ratio = abs(front_knee[0] - front_ankle[0]) / leg_length
        return drift_ratio <= self.MAX_HEAD_DRIFT_RATIO

    def update(self, front_hip, front_knee, front_ankle,
               back_hip, back_knee, back_ankle):
        """
        Args:
            front_hip, front_knee, front_ankle: (x, y) tuples for the front leg.
            back_hip, back_knee, back_ankle: (x, y) tuples for the back leg.

        Returns:
            dict with keys: exercise, front_angle, back_angle, hold_time, stage, feedback
        """
        front_angle = self.calculator.calculate(front_hip, front_knee, front_ankle)
        back_angle = self.calculator.calculate(back_hip, back_knee, back_ankle)

        self.front_angle = front_angle
        self.back_angle = back_angle

        front_ok = self.FRONT_KNEE_MIN <= front_angle <= self.FRONT_KNEE_MAX
        back_ok = self.BACK_KNEE_MIN <= back_angle <= self.BACK_KNEE_MAX
        arm_level_ok = self._arm_level_ok(front_hip, back_hip)
        torso_ok = self._torso_vertical_ok(front_hip, back_hip, front_ankle, back_ankle)
        head_ok = self._head_direction_ok(front_knee, front_ankle, front_hip)

        if front_ok and back_ok and arm_level_ok and torso_ok and head_ok:
            if self._hold_start_time is None:
                self._hold_start_time = time.time()
            self.hold_time = time.time() - self._hold_start_time
            self.stage = "HOLD"
            self.feedback = "Perfect Warrior II"

        else:
            self._hold_start_time = None
            self.hold_time = 0.0
            self.stage = "ADJUST"

            # Priority order: leg form first, then upper-body/gaze checks.
            if not front_ok:
                self.feedback = "Bend Front Knee"
            elif not back_ok:
                self.feedback = "Straighten Back Leg"
            elif not arm_level_ok:
                self.feedback = "Raise Arms"
            elif not head_ok:
                self.feedback = "Look Forward"
            elif not torso_ok:
                self.feedback = "Look Forward"
            else:
                self.feedback = "Adjust Your Pose"

        return {
            "exercise": self.name,
            "front_angle": round(front_angle, 1),
            "back_angle": round(back_angle, 1),
            "hold_time": round(self.hold_time, 1),
            "stage": self.stage,
            "feedback": self.feedback,
        }