"""
core/drawing.py
================

Rendering / visualization layer for PoseAI - Real-Time AI Fitness Trainer.

This module is responsible for turning raw MediaPipe Pose Landmarker
Tasks API results into a polished, production-grade on-screen overlay:
a custom-drawn skeleton (no mp.solutions.drawing_utils dependency),
per-joint angle readouts, exercise-aware joint highlighting, a modern
translucent dashboard, FPS meter, confidence indicator, reference grid
and body-center marker.

Compatible ONLY with:
    mediapipe.tasks.python.vision.PoseLandmarker
    (result.pose_landmarks -> List[List[NormalizedLandmark]])

NOT compatible with the legacy mp.solutions.pose Solutions API.

Author: PoseAI Engineering Team
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

try:
    # Preferred: use the project's shared angle calculation utilities.
    from core.angle_calculator import AngleCalculator
except Exception:  # pragma: no cover - defensive import fallback
    AngleCalculator = None  # type: ignore


# --------------------------------------------------------------------------- #
# LANDMARK INDEX CONSTANTS (MediaPipe Pose - 33 landmarks)
# --------------------------------------------------------------------------- #

NOSE = 0
LEFT_EYE_INNER = 1
LEFT_EYE = 2
LEFT_EYE_OUTER = 3
RIGHT_EYE_INNER = 4
RIGHT_EYE = 5
RIGHT_EYE_OUTER = 6
LEFT_EAR = 7
RIGHT_EAR = 8
MOUTH_LEFT = 9
MOUTH_RIGHT = 10
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_PINKY = 17
RIGHT_PINKY = 18
LEFT_INDEX = 19
RIGHT_INDEX = 20
LEFT_THUMB = 21
RIGHT_THUMB = 22
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_HEEL = 29
RIGHT_HEEL = 30
LEFT_FOOT_INDEX = 31
RIGHT_FOOT_INDEX = 32

TOTAL_LANDMARKS = 33

LANDMARK_NAMES: Dict[int, str] = {
    NOSE: "NOSE",
    LEFT_EYE_INNER: "L_EYE_IN",
    LEFT_EYE: "L_EYE",
    LEFT_EYE_OUTER: "L_EYE_OUT",
    RIGHT_EYE_INNER: "R_EYE_IN",
    RIGHT_EYE: "R_EYE",
    RIGHT_EYE_OUTER: "R_EYE_OUT",
    LEFT_EAR: "L_EAR",
    RIGHT_EAR: "R_EAR",
    MOUTH_LEFT: "MOUTH_L",
    MOUTH_RIGHT: "MOUTH_R",
    LEFT_SHOULDER: "L_SHOULDER",
    RIGHT_SHOULDER: "R_SHOULDER",
    LEFT_ELBOW: "L_ELBOW",
    RIGHT_ELBOW: "R_ELBOW",
    LEFT_WRIST: "L_WRIST",
    RIGHT_WRIST: "R_WRIST",
    LEFT_PINKY: "L_PINKY",
    RIGHT_PINKY: "R_PINKY",
    LEFT_INDEX: "L_INDEX",
    RIGHT_INDEX: "R_INDEX",
    LEFT_THUMB: "L_THUMB",
    RIGHT_THUMB: "R_THUMB",
    LEFT_HIP: "L_HIP",
    RIGHT_HIP: "R_HIP",
    LEFT_KNEE: "L_KNEE",
    RIGHT_KNEE: "R_KNEE",
    LEFT_ANKLE: "L_ANKLE",
    RIGHT_ANKLE: "R_ANKLE",
    LEFT_HEEL: "L_HEEL",
    RIGHT_HEEL: "R_HEEL",
    LEFT_FOOT_INDEX: "L_FOOT",
    RIGHT_FOOT_INDEX: "R_FOOT",
}


# --------------------------------------------------------------------------- #
# SKELETON TOPOLOGY (custom - independent of mp.solutions.drawing_utils)
# --------------------------------------------------------------------------- #
# Each entry: (start_index, end_index, category)
# category in {"head", "torso", "left", "right"} drives line color.
# This topology is anatomically ordered (shoulder->elbow->wrist->hand,
# hip->knee->ankle->foot) so connections never visually "jump" across
# the body, which is what caused the perceived front/behind-arm overlap
# reported for fast movements.

BODY_CONNECTIONS: List[Tuple[int, int, str]] = [
    # ---- Head ----
    (NOSE, LEFT_EYE_INNER, "head"),
    (LEFT_EYE_INNER, LEFT_EYE, "head"),
    (LEFT_EYE, LEFT_EYE_OUTER, "head"),
    (LEFT_EYE_OUTER, LEFT_EAR, "head"),
    (NOSE, RIGHT_EYE_INNER, "head"),
    (RIGHT_EYE_INNER, RIGHT_EYE, "head"),
    (RIGHT_EYE, RIGHT_EYE_OUTER, "head"),
    (RIGHT_EYE_OUTER, RIGHT_EAR, "head"),
    (MOUTH_LEFT, MOUTH_RIGHT, "head"),

    # ---- Torso ----
    (LEFT_SHOULDER, RIGHT_SHOULDER, "torso"),
    (LEFT_HIP, RIGHT_HIP, "torso"),
    (LEFT_SHOULDER, LEFT_HIP, "torso"),
    (RIGHT_SHOULDER, RIGHT_HIP, "torso"),

    # ---- Left arm ----
    (LEFT_SHOULDER, LEFT_ELBOW, "left"),
    (LEFT_ELBOW, LEFT_WRIST, "left"),
    (LEFT_WRIST, LEFT_THUMB, "left"),
    (LEFT_WRIST, LEFT_INDEX, "left"),
    (LEFT_WRIST, LEFT_PINKY, "left"),
    (LEFT_INDEX, LEFT_PINKY, "left"),

    # ---- Right arm ----
    (RIGHT_SHOULDER, RIGHT_ELBOW, "right"),
    (RIGHT_ELBOW, RIGHT_WRIST, "right"),
    (RIGHT_WRIST, RIGHT_THUMB, "right"),
    (RIGHT_WRIST, RIGHT_INDEX, "right"),
    (RIGHT_WRIST, RIGHT_PINKY, "right"),
    (RIGHT_INDEX, RIGHT_PINKY, "right"),

    # ---- Left leg / foot ----
    (LEFT_HIP, LEFT_KNEE, "left"),
    (LEFT_KNEE, LEFT_ANKLE, "left"),
    (LEFT_ANKLE, LEFT_HEEL, "left"),
    (LEFT_HEEL, LEFT_FOOT_INDEX, "left"),
    (LEFT_ANKLE, LEFT_FOOT_INDEX, "left"),

    # ---- Right leg / foot ----
    (RIGHT_HIP, RIGHT_KNEE, "right"),
    (RIGHT_KNEE, RIGHT_ANKLE, "right"),
    (RIGHT_ANKLE, RIGHT_HEEL, "right"),
    (RIGHT_HEEL, RIGHT_FOOT_INDEX, "right"),
    (RIGHT_ANKLE, RIGHT_FOOT_INDEX, "right"),
]


# --------------------------------------------------------------------------- #
# EXERCISE -> JOINTS OF INTEREST (used for selective highlighting)
# --------------------------------------------------------------------------- #

EXERCISE_JOINTS: Dict[str, List[int]] = {
    "bicep_curl": [LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST,
                   RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST],
    "pushup": [LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST, LEFT_HIP,
               RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST, RIGHT_HIP],
    "squat": [LEFT_HIP, LEFT_KNEE, LEFT_ANKLE,
              RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE],
    "plank": [LEFT_SHOULDER, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE,
              RIGHT_SHOULDER, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE],
    "shoulder_press": [LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST,
                        RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST],
    "lunge": [LEFT_HIP, LEFT_KNEE, LEFT_ANKLE,
              RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE],
    "triceps_pushdown": [LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST,
                          RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST],
    "jumping_jacks": [LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP,
                       LEFT_WRIST, RIGHT_WRIST, LEFT_ANKLE, RIGHT_ANKLE],
    "burpees": [LEFT_SHOULDER, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE,
                RIGHT_SHOULDER, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE],
    "goblet_squat": [LEFT_HIP, LEFT_KNEE, LEFT_ANKLE,
                      RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE],
    "warrior2": [LEFT_HIP, LEFT_KNEE, LEFT_ANKLE,
                 RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE],
}


# --------------------------------------------------------------------------- #
# COLOR PALETTE (BGR - OpenCV convention)
# --------------------------------------------------------------------------- #

COLOR_HEAD = (0, 255, 255)        # Yellow
COLOR_LEFT = (0, 200, 0)          # Green
COLOR_RIGHT = (255, 120, 0)       # Blue
COLOR_TORSO = (245, 245, 245)     # White
COLOR_INACTIVE = (130, 130, 130)  # Gray
COLOR_HIGHLIGHT = (0, 140, 255)   # Orange
COLOR_TEXT = (255, 255, 255)      # White
COLOR_TEXT_DIM = (200, 200, 200)  # Light gray
COLOR_DASH_BG = (20, 20, 20)      # Dark translucent panel background
COLOR_GOOD = (0, 200, 0)          # Green (status good)
COLOR_WARN = (0, 210, 255)        # Yellow (status warn)
COLOR_BAD = (0, 0, 255)           # Red (status bad)
COLOR_GRID = (90, 90, 90)         # Faint grid lines
COLOR_CENTER = (255, 0, 255)      # Magenta body-center marker

_CATEGORY_COLOR = {
    "head": COLOR_HEAD,
    "torso": COLOR_TORSO,
    "left": COLOR_LEFT,
    "right": COLOR_RIGHT,
}

FONT = cv2.FONT_HERSHEY_SIMPLEX


class PoseDrawer:
    """
    Draws a fully custom pose overlay (skeleton, angles, dashboard, FPS,
    confidence, grid, body center) on top of a video frame, built purely
    with OpenCV primitives.

    Sizing (joint radius / line thickness) is computed per-frame from the
    frame's own resolution so the skeleton looks correct at any camera
    resolution instead of using fixed pixel constants tuned for one size.

    A small per-joint visibility "hysteresis" (Schmitt-trigger style) is
    kept in `_visible_state` so a landmark's confidence hovering right at
    the threshold doesn't cause the joint/connection to flicker on/off
    every frame - it needs to clearly cross above the threshold to turn
    ON and clearly drop below a lower threshold to turn OFF.
    """

    # ---- Static drawing configuration (reused every frame - no re-alloc) ---
    JOINT_RADIUS: int = 6
    LINE_THICKNESS: int = 3
    HIGHLIGHT_RADIUS: int = 9
    LABEL_FONT_SCALE: float = 0.4
    ANGLE_FONT_SCALE: float = 0.5
    TEXT_FONT_SCALE: float = 0.6
    VISIBILITY_THRESHOLD: float = 0.5

    # Lower "release" threshold for the visibility hysteresis. A joint
    # that is currently considered visible only becomes invisible once
    # its score drops below this (lower than VISIBILITY_THRESHOLD),
    # while a joint that is currently invisible only becomes visible once
    # it rises above VISIBILITY_THRESHOLD. This gap prevents flicker for
    # scores oscillating around 0.5.
    VISIBILITY_RELEASE_THRESHOLD: float = 0.35

    # Reference frame width used to scale JOINT_RADIUS / LINE_THICKNESS
    # proportionally. A 640px-wide frame renders at the base sizes above;
    # larger/smaller frames scale up/down accordingly so the skeleton
    # keeps sensible proportions on any camera resolution.
    _REFERENCE_WIDTH: int = 640
    _MIN_SCALE: float = 0.5
    _MAX_SCALE: float = 2.5

    def __init__(self) -> None:
        """Initialize the drawer and its (stateless, reusable) angle engine."""
        self.angle_calculator = AngleCalculator() if AngleCalculator else None

        # Joint groups used to compute the headline angles shown on screen.
        # Each tuple: (label, point_a, point_b(vertex), point_c)
        self._angle_defs: List[Tuple[str, int, int, int]] = [
            ("L-Elbow", LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST),
            ("R-Elbow", RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST),
            ("L-Shoulder", LEFT_ELBOW, LEFT_SHOULDER, LEFT_HIP),
            ("R-Shoulder", RIGHT_ELBOW, RIGHT_SHOULDER, RIGHT_HIP),
            ("L-Hip", LEFT_SHOULDER, LEFT_HIP, LEFT_KNEE),
            ("R-Hip", RIGHT_SHOULDER, RIGHT_HIP, RIGHT_KNEE),
            ("L-Knee", LEFT_HIP, LEFT_KNEE, LEFT_ANKLE),
            ("R-Knee", RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE),
        ]

        # Per-landmark-index hysteresis state: True = currently drawn as
        # "visible/confident". Persists across frames so a single noisy
        # frame near the threshold can't toggle a joint on and off.
        self._visible_state: Dict[int, bool] = {}

        # Cached per-frame sizing (recomputed once per draw() call, then
        # reused by every helper method that needs it, instead of every
        # helper recalculating frame.shape and scale independently).
        self._joint_radius: int = self.JOINT_RADIUS
        self._line_thickness: int = self.LINE_THICKNESS
        self._highlight_radius: int = self.HIGHLIGHT_RADIUS

    # ------------------------------------------------------------------ #
    # MAIN ENTRY POINT
    # ------------------------------------------------------------------ #

    def draw(
        self,
        frame: np.ndarray,
        result: Any,
        exercise_name: Optional[str] = None,
        workout_data: Optional[Dict[str, Any]] = None,
        fps: Optional[float] = None,
        show_labels: bool = False,
        show_angles: bool = True,
        show_confidence: bool = True,
        show_grid: bool = False,
        show_body_center: bool = False,
    ) -> np.ndarray:
        """
        Render the complete overlay for a single frame.

        Args:
            frame: BGR frame (numpy array) to draw on, modified in place.
            result: PoseLandmarker Tasks API result (`result.pose_landmarks`).
                This should be the most recently processed detection result
                for this frame - passing a stale/previous-frame result is
                what causes visible skeleton lag, so callers should always
                supply the result produced for the frame being drawn.
            exercise_name: Active exercise key (e.g. "squat", "bicep_curl").
            workout_data: Dict with dashboard fields (reps, stage, feedback...).
            fps: Current frames-per-second, if available.
            show_labels: Whether to draw numeric landmark ID labels.
            show_angles: Whether to draw joint angle readouts.
            show_confidence: Whether to draw the confidence indicator.
            show_grid: Whether to draw the reference grid.
            show_body_center: Whether to draw the body center marker.

        Returns:
            The frame with the overlay drawn on it. Never raises - if no
            pose is detected the original frame is returned untouched.
        """
        if frame is None:
            return frame

        # Recompute proportional sizing for this frame's resolution before
        # any drawing happens, so every helper below uses consistent,
        # correctly-scaled joint radii and line thickness.
        self._update_scale(frame)

        if show_grid:
            self.draw_grid(frame)

        if result is None or not getattr(result, "pose_landmarks", None):
            # No detection this frame - clear hysteresis state so stale
            # "visible" joints don't ghost-persist once the person leaves
            # the frame and later reappears, then bail out safely.
            self._visible_state.clear()
            if fps is not None:
                self.draw_fps(frame, fps)
            return frame

        try:
            landmarks = result.pose_landmarks[0]
        except (IndexError, TypeError):
            self._visible_state.clear()
            if fps is not None:
                self.draw_fps(frame, fps)
            return frame

        if not landmarks or len(landmarks) < TOTAL_LANDMARKS:
            if fps is not None:
                self.draw_fps(frame, fps)
            return frame

        # Skeleton - drawn from the exact landmark list passed in for this
        # frame, so the overlay always matches what the detector/workout
        # logic just computed rather than a previous frame's positions.
        self.draw_connections(frame, landmarks)
        self.draw_landmarks(frame, landmarks)

        # Exercise-aware highlighting
        if exercise_name:
            self.draw_exercise_highlight(frame, landmarks, exercise_name)

        # Optional overlays
        if show_labels:
            self.draw_joint_labels(frame, landmarks)

        if show_angles:
            self.draw_joint_angles(frame, landmarks)

        if show_body_center:
            self.draw_body_center(frame, landmarks)

        if show_confidence:
            self.draw_confidence(frame, landmarks)

        if workout_data:
            self.draw_dashboard(frame, workout_data)

        if fps is not None:
            self.draw_fps(frame, fps)

        return frame

    # ------------------------------------------------------------------ #
    # INTERNAL HELPERS
    # ------------------------------------------------------------------ #

    def _update_scale(self, frame: np.ndarray) -> None:
        """
        Recompute joint radius / line thickness proportionally to the
        current frame's width, relative to a 640px reference resolution.

        Keeps the skeleton looking correctly proportioned whether the
        camera feed is a small 480p preview or a full 1080p capture,
        instead of drawing fixed-pixel joints that look tiny on large
        frames or oversized/imprecise on small ones.
        """
        height, width = frame.shape[:2]
        if width <= 0:
            scale = 1.0
        else:
            scale = width / float(self._REFERENCE_WIDTH)
            scale = min(max(scale, self._MIN_SCALE), self._MAX_SCALE)

        self._joint_radius = max(2, int(round(self.JOINT_RADIUS * scale)))
        self._line_thickness = max(1, int(round(self.LINE_THICKNESS * scale)))
        self._highlight_radius = max(3, int(round(self.HIGHLIGHT_RADIUS * scale)))

    @staticmethod
    def _is_finite_point(landmark: Any) -> bool:
        """
        Guard against invalid landmark coordinates (NaN/inf or missing
        x/y attributes) that MediaPipe can occasionally emit for a
        landmark it briefly loses track of. Drawing these directly would
        either crash cv2 or render a joint at a nonsensical position, so
        every landmark is validated before it is projected to pixels.
        """
        x = getattr(landmark, "x", None)
        y = getattr(landmark, "y", None)
        if x is None or y is None:
            return False
        try:
            return math.isfinite(float(x)) and math.isfinite(float(y))
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _to_pixel(landmark: Any, width: int, height: int) -> Tuple[int, int]:
        """Convert a normalized landmark to clamped pixel coordinates."""
        x = int(min(max(landmark.x, 0.0), 1.0) * width)
        y = int(min(max(landmark.y, 0.0), 1.0) * height)
        return x, y

    @staticmethod
    def _visibility_of(landmark: Any) -> float:
        """Safely fetch a landmark's visibility score (defaults to 1.0)."""
        return float(getattr(landmark, "visibility", 1.0) or 1.0)

    def _is_stable_visible(self, index: int, landmark: Any) -> bool:
        """
        Apply visibility hysteresis for a given landmark index.

        A joint currently marked visible stays visible until its score
        drops below VISIBILITY_RELEASE_THRESHOLD; a joint currently
        marked invisible only becomes visible once its score rises above
        VISIBILITY_THRESHOLD. This dead-band between the two thresholds
        is what eliminates on/off flicker for borderline-confidence
        landmarks (a common issue during fast, blurry movement).

        Also treats non-finite/invalid coordinates as not visible,
        regardless of the reported visibility score.
        """
        if not self._is_finite_point(landmark):
            self._visible_state[index] = False
            return False

        visibility = self._visibility_of(landmark)
        currently_visible = self._visible_state.get(index, False)

        if currently_visible:
            stable = visibility >= self.VISIBILITY_RELEASE_THRESHOLD
        else:
            stable = visibility >= self.VISIBILITY_THRESHOLD

        self._visible_state[index] = stable
        return stable

    @staticmethod
    def _normalize_exercise_key(exercise_name: str) -> str:
        """Normalize an exercise name into the EXERCISE_JOINTS key format."""
        return exercise_name.strip().lower().replace(" ", "_").replace("-", "_")

    def _angle_between(self, a: Tuple[float, float],
                        b: Tuple[float, float],
                        c: Tuple[float, float]) -> float:
        """
        Compute the angle (degrees) at vertex `b` formed by points a-b-c.
        Uses AngleCalculator if available, otherwise falls back to a local
        numpy implementation so this module never hard-crashes on a
        missing dependency.
        """
        if self.angle_calculator is not None:
            try:
                return float(self.angle_calculator.calculate_angle(a, b, c))
            except Exception:
                pass  # fall through to local implementation

        a_arr, b_arr, c_arr = np.array(a), np.array(b), np.array(c)
        ba = a_arr - b_arr
        bc = c_arr - b_arr
        denom = (np.linalg.norm(ba) * np.linalg.norm(bc)) or 1e-6
        cosine = np.dot(ba, bc) / denom
        cosine = np.clip(cosine, -1.0, 1.0)
        return float(np.degrees(np.arccos(cosine)))

    # ------------------------------------------------------------------ #
    # SKELETON DRAWING
    # ------------------------------------------------------------------ #

    def draw_landmarks(self, frame: np.ndarray, landmarks: Sequence[Any]) -> None:
        """Draw every visible landmark as an anti-aliased filled circle."""
        height, width = frame.shape[:2]
        for idx, lm in enumerate(landmarks):
            if not self._is_finite_point(lm):
                continue
            stable_visible = self._is_stable_visible(idx, lm)
            point = self._to_pixel(lm, width, height)
            color = COLOR_INACTIVE if not stable_visible else self._joint_color(idx)
            self.draw_joint(frame, point, color)

    def _joint_color(self, index: int) -> Tuple[int, int, int]:
        """Default (non-highlighted) color for a given landmark index."""
        if index <= RIGHT_EAR or index in (MOUTH_LEFT, MOUTH_RIGHT):
            return COLOR_HEAD
        if index in (LEFT_SHOULDER, LEFT_HIP) or index % 2 == 1 and index >= LEFT_SHOULDER:
            return COLOR_LEFT
        return COLOR_RIGHT

    def draw_joint(
        self,
        frame: np.ndarray,
        point: Tuple[int, int],
        color: Tuple[int, int, int],
    ) -> None:
        """Draw a single filled, anti-aliased joint circle with a dark ring."""
        cv2.circle(frame, point, self._joint_radius + 1, (30, 30, 30), -1, cv2.LINE_AA)
        cv2.circle(frame, point, self._joint_radius, color, -1, cv2.LINE_AA)

    def draw_connections(self, frame: np.ndarray, landmarks: Sequence[Any]) -> None:
        """Draw thick, anti-aliased skeleton connection lines."""
        height, width = frame.shape[:2]
        for start_idx, end_idx, category in BODY_CONNECTIONS:
            if start_idx >= len(landmarks) or end_idx >= len(landmarks):
                continue

            start_lm, end_lm = landmarks[start_idx], landmarks[end_idx]

            # Skip the connection entirely rather than drawing a line to
            # a garbage (0,0) point - this is what previously caused
            # lines to visually snap across the frame or overlap the
            # wrong limb when a landmark briefly lost tracking.
            if not self._is_finite_point(start_lm) or not self._is_finite_point(end_lm):
                continue

            start_stable = self._is_stable_visible(start_idx, start_lm)
            end_stable = self._is_stable_visible(end_idx, end_lm)

            color = COLOR_INACTIVE if not (start_stable and end_stable) else _CATEGORY_COLOR.get(category, COLOR_TORSO)

            start_point = self._to_pixel(start_lm, width, height)
            end_point = self._to_pixel(end_lm, width, height)
            cv2.line(frame, start_point, end_point, color, self._line_thickness, cv2.LINE_AA)

    def draw_joint_labels(self, frame: np.ndarray, landmarks: Sequence[Any]) -> None:
        """Draw the numeric landmark ID next to each joint (debug/education)."""
        height, width = frame.shape[:2]
        for idx, lm in enumerate(landmarks):
            if not self._is_finite_point(lm) or not self._is_stable_visible(idx, lm):
                continue
            point = self._to_pixel(lm, width, height)
            label_point = (point[0] + 8, point[1] - 8)
            self.draw_text(
                frame, str(idx), label_point,
                font_scale=self.LABEL_FONT_SCALE, color=COLOR_TEXT_DIM, thickness=1,
            )

    # ------------------------------------------------------------------ #
    # ANGLES
    # ------------------------------------------------------------------ #

    def draw_joint_angles(self, frame: np.ndarray, landmarks: Sequence[Any]) -> None:
        """
        Compute and render the headline biomechanical angles (elbow,
        shoulder, hip, knee) plus derived neck/torso/back angles.
        """
        height, width = frame.shape[:2]

        # Standard triplet joint angles (elbow / shoulder / hip / knee).
        for label, a_idx, b_idx, c_idx in self._angle_defs:
            if max(a_idx, b_idx, c_idx) >= len(landmarks):
                continue
            a_lm, b_lm, c_lm = landmarks[a_idx], landmarks[b_idx], landmarks[c_idx]

            if not (self._is_finite_point(a_lm) and self._is_finite_point(b_lm)
                    and self._is_finite_point(c_lm)):
                continue

            if min(self._visibility_of(a_lm), self._visibility_of(b_lm),
                   self._visibility_of(c_lm)) < self.VISIBILITY_THRESHOLD:
                continue

            angle = self._angle_between((a_lm.x, a_lm.y), (b_lm.x, b_lm.y), (c_lm.x, c_lm.y))
            vertex_point = self._to_pixel(b_lm, width, height)
            self.draw_angle(frame, vertex_point, angle)

        # Derived composite angles: neck, torso lean, back straightness.
        self._draw_derived_angles(frame, landmarks, width, height)

    def _draw_derived_angles(
        self, frame: np.ndarray, landmarks: Sequence[Any], width: int, height: int
    ) -> None:
        """Draw neck, torso and back angles which use midpoints of joints."""
        required = [NOSE, LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP,
                    LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE]
        if max(required) >= len(landmarks):
            return

        for idx in required:
            if not self._is_finite_point(landmarks[idx]):
                return

        nose = landmarks[NOSE]
        mid_shoulder = self._midpoint(landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER])
        mid_hip = self._midpoint(landmarks[LEFT_HIP], landmarks[RIGHT_HIP])
        mid_knee = self._midpoint(landmarks[LEFT_KNEE], landmarks[RIGHT_KNEE])
        mid_ankle = self._midpoint(landmarks[LEFT_ANKLE], landmarks[RIGHT_ANKLE])

        # Neck angle: nose - mid_shoulder - mid_hip
        neck_angle = self._angle_between((nose.x, nose.y), mid_shoulder, mid_hip)
        neck_point = (int(mid_shoulder[0] * width), int(mid_shoulder[1] * height) - 25)
        self.draw_angle(frame, neck_point, neck_angle)

        # Torso angle: mid_shoulder - mid_hip - mid_knee
        torso_angle = self._angle_between(mid_shoulder, mid_hip, mid_knee)
        torso_point = (int(mid_hip[0] * width), int(mid_hip[1] * height))
        self.draw_angle(frame, torso_point, torso_angle)

        # Back angle: mid_shoulder - mid_hip - mid_ankle (straightness for plank)
        back_angle = self._angle_between(mid_shoulder, mid_hip, mid_ankle)
        back_point = (int(mid_hip[0] * width) + 40, int(mid_hip[1] * height) + 20)
        self.draw_angle(frame, back_point, back_angle)

    @staticmethod
    def _midpoint(lm_a: Any, lm_b: Any) -> Tuple[float, float]:
        """Return the normalized-coordinate midpoint between two landmarks."""
        return ((lm_a.x + lm_b.x) / 2.0, (lm_a.y + lm_b.y) / 2.0)

    def draw_angle(self, frame: np.ndarray, point: Tuple[int, int], angle: float) -> None:
        """Render a rounded label bubble with the angle value at `point`."""
        text = f"{int(round(angle))}deg"
        text = f"{int(round(angle))}\u00b0"
        (text_w, text_h), _ = cv2.getTextSize(text, FONT, self.ANGLE_FONT_SCALE, 1)

        pad = 4
        pt1 = (point[0] - text_w // 2 - pad, point[1] - text_h - pad)
        pt2 = (point[0] + text_w // 2 + pad, point[1] + pad)

        overlay = frame.copy()
        self.draw_rounded_rectangle(overlay, pt1, pt2, color=(15, 15, 15), radius=6)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, dst=frame)

        text_origin = (point[0] - text_w // 2, point[1] - pad // 2)
        self.draw_text(
            frame, text, text_origin,
            font_scale=self.ANGLE_FONT_SCALE, color=COLOR_HIGHLIGHT, thickness=1,
        )

    # ------------------------------------------------------------------ #
    # EXERCISE HIGHLIGHTING
    # ------------------------------------------------------------------ #

    def draw_exercise_highlight(
        self, frame: np.ndarray, landmarks: Sequence[Any], exercise_name: str
    ) -> None:
        """Highlight (in orange, with a larger radius) joints relevant to the
        currently active exercise, so the user can see what is being tracked."""
        key = self._normalize_exercise_key(exercise_name)
        joint_indices = EXERCISE_JOINTS.get(key)
        if not joint_indices:
            return

        height, width = frame.shape[:2]
        for idx in joint_indices:
            if idx >= len(landmarks):
                continue
            lm = landmarks[idx]
            if not self._is_finite_point(lm) or not self._is_stable_visible(idx, lm):
                continue
            point = self._to_pixel(lm, width, height)
            cv2.circle(frame, point, self._highlight_radius, COLOR_HIGHLIGHT, 2, cv2.LINE_AA)

    # ------------------------------------------------------------------ #
    # DASHBOARD / HUD
    # ------------------------------------------------------------------ #

    def draw_dashboard(self, frame: np.ndarray, workout_data: Dict[str, Any]) -> None:
        """
        Draw a modern, dark, translucent dashboard panel in the top-left
        corner summarizing the current workout state.

        Expected (all optional) keys in `workout_data`:
            exercise, reps, stage, feedback, fps, angle, confidence,
            resolution (tuple[int, int]) or width/height.
        """
        height, width = frame.shape[:2]
        panel_w, panel_h = 300, 210
        pt1, pt2 = (15, 15), (15 + panel_w, 15 + panel_h)

        overlay = frame.copy()
        self.draw_rounded_rectangle(overlay, pt1, pt2, color=COLOR_DASH_BG, radius=14)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, dst=frame)

        cv2.rectangle(frame, pt1, pt2, (70, 70, 70), 1, cv2.LINE_AA)

        exercise = str(workout_data.get("exercise", "N/A")).upper()
        reps = workout_data.get("reps", 0)
        stage = str(workout_data.get("stage", "-")).upper()
        feedback = str(workout_data.get("feedback", "Keep going!"))
        fps_val = workout_data.get("fps")
        angle_val = workout_data.get("angle")
        confidence = workout_data.get("confidence")
        resolution = workout_data.get("resolution", (width, height))

        x, y = pt1[0] + 16, pt1[1] + 28
        line_gap = 26

        self.draw_text(frame, "POSE AI DASHBOARD", (x, y),
                        font_scale=0.55, color=COLOR_HIGHLIGHT, thickness=2)
        y += line_gap + 4

        self.draw_text(frame, f"Exercise : {exercise}", (x, y), color=COLOR_TEXT)
        y += line_gap
        self.draw_text(frame, f"Reps     : {reps}", (x, y), color=COLOR_TEXT)
        y += line_gap
        self.draw_text(frame, f"Stage    : {stage}", (x, y), color=COLOR_TEXT)
        y += line_gap

        if angle_val is not None:
            self.draw_text(frame, f"Angle    : {int(round(angle_val))}\u00b0", (x, y), color=COLOR_TEXT)
            y += line_gap

        if confidence is not None:
            conf_color = self._status_color(confidence, 0.8, 0.5)
            self.draw_text(frame, f"Confid.  : {int(confidence * 100)}%", (x, y), color=conf_color)
            y += line_gap

        if fps_val is not None:
            fps_color = self._status_color(fps_val, 25, 15)
            self.draw_text(frame, f"FPS      : {int(fps_val)}", (x, y), color=fps_color)
            y += line_gap

        self.draw_text(frame, f"Res      : {resolution[0]}x{resolution[1]}", (x, y), color=COLOR_TEXT_DIM)
        y += line_gap

        self.draw_text(frame, f"> {feedback}", (x, y), font_scale=0.5, color=COLOR_WARN, thickness=1)

    @staticmethod
    def _status_color(value: float, good_threshold: float, warn_threshold: float) -> Tuple[int, int, int]:
        """Return green/yellow/red based on where `value` sits vs thresholds."""
        if value > good_threshold:
            return COLOR_GOOD
        if value > warn_threshold:
            return COLOR_WARN
        return COLOR_BAD

    # ------------------------------------------------------------------ #
    # FPS METER
    # ------------------------------------------------------------------ #

    def draw_fps(self, frame: np.ndarray, fps: float) -> None:
        """Draw an FPS readout in the top-right corner, color-coded by speed."""
        height, width = frame.shape[:2]
        color = self._status_color(fps, 25, 15)
        text = f"FPS: {int(round(fps))}"

        (text_w, text_h), _ = cv2.getTextSize(text, FONT, self.TEXT_FONT_SCALE, 2)
        margin = 15
        pt2 = (width - margin, margin + text_h + 12)
        pt1 = (pt2[0] - text_w - 20, margin)

        overlay = frame.copy()
        self.draw_rounded_rectangle(overlay, pt1, pt2, color=COLOR_DASH_BG, radius=8)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, dst=frame)

        text_origin = (pt1[0] + 10, pt2[1] - 10)
        self.draw_text(frame, text, text_origin, font_scale=self.TEXT_FONT_SCALE, color=color, thickness=2)

    # ------------------------------------------------------------------ #
    # CONFIDENCE INDICATOR
    # ------------------------------------------------------------------ #

    def draw_confidence(self, frame: np.ndarray, landmarks: Sequence[Any]) -> None:
        """
        Draw an average pose-detection confidence indicator in the
        bottom-left corner, color-coded green/yellow/red.
        """
        if not landmarks:
            return

        visibilities = [self._visibility_of(lm) for lm in landmarks if self._is_finite_point(lm)]
        avg_visibility = float(np.mean(visibilities)) if visibilities else 0.0
        color = self._status_color(avg_visibility, 0.8, 0.5)

        height, width = frame.shape[:2]
        text = f"Confidence: {int(avg_visibility * 100)}%"
        position = (15, height - 20)

        (text_w, text_h), _ = cv2.getTextSize(text, FONT, self.TEXT_FONT_SCALE, 2)
        pt1 = (position[0] - 8, position[1] - text_h - 10)
        pt2 = (position[0] + text_w + 8, position[1] + 8)

        overlay = frame.copy()
        self.draw_rounded_rectangle(overlay, pt1, pt2, color=COLOR_DASH_BG, radius=8)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, dst=frame)

        cv2.circle(frame, (pt1[0] + 14, position[1] - text_h // 2), 5, color, -1, cv2.LINE_AA)
        self.draw_text(frame, text, (pt1[0] + 26, position[1]),
                        font_scale=self.TEXT_FONT_SCALE, color=color, thickness=2)

    # ------------------------------------------------------------------ #
    # BODY CENTER
    # ------------------------------------------------------------------ #

    def draw_body_center(self, frame: np.ndarray, landmarks: Sequence[Any]) -> None:
        """
        Draw a crosshair marker at the approximate body center of mass
        (midpoint of shoulders and hips) - useful for balance-sensitive
        exercises such as plank and squat.
        """
        required = [LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP]
        if max(required) >= len(landmarks):
            return

        for idx in required:
            if not self._is_finite_point(landmarks[idx]):
                return

        height, width = frame.shape[:2]
        shoulders = self._midpoint(landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER])
        hips = self._midpoint(landmarks[LEFT_HIP], landmarks[RIGHT_HIP])
        center_norm = ((shoulders[0] + hips[0]) / 2.0, (shoulders[1] + hips[1]) / 2.0)
        center = (int(center_norm[0] * width), int(center_norm[1] * height))

        size = max(6, int(round(12 * (self._joint_radius / float(self.JOINT_RADIUS)))))
        cv2.line(frame, (center[0] - size, center[1]), (center[0] + size, center[1]),
                  COLOR_CENTER, 2, cv2.LINE_AA)
        cv2.line(frame, (center[0], center[1] - size), (center[0], center[1] + size),
                  COLOR_CENTER, 2, cv2.LINE_AA)
        cv2.circle(frame, center, size + 4, COLOR_CENTER, 1, cv2.LINE_AA)

    # ------------------------------------------------------------------ #
    # REFERENCE GRID
    # ------------------------------------------------------------------ #

    def draw_grid(self, frame: np.ndarray) -> None:
        """Draw a faint rule-of-thirds style reference grid across the frame."""
        height, width = frame.shape[:2]
        overlay = frame.copy()

        for fraction in (1 / 3, 2 / 3):
            x = int(width * fraction)
            y = int(height * fraction)
            cv2.line(overlay, (x, 0), (x, height), COLOR_GRID, 1, cv2.LINE_AA)
            cv2.line(overlay, (0, y), (width, y), COLOR_GRID, 1, cv2.LINE_AA)

        cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, dst=frame)

    # ------------------------------------------------------------------ #
    # GENERIC PRIMITIVES
    # ------------------------------------------------------------------ #

    def draw_text(
        self,
        frame: np.ndarray,
        text: str,
        position: Tuple[int, int],
        font_scale: float = 0.6,
        color: Tuple[int, int, int] = COLOR_TEXT,
        thickness: int = 2,
    ) -> None:
        """Draw anti-aliased text with a subtle drop shadow for readability."""
        shadow_pos = (position[0] + 1, position[1] + 1)
        cv2.putText(frame, text, shadow_pos, FONT, font_scale, (0, 0, 0),
                    thickness + 1, cv2.LINE_AA)
        cv2.putText(frame, text, position, FONT, font_scale, color,
                    thickness, cv2.LINE_AA)

    def draw_rounded_rectangle(
        self,
        frame: np.ndarray,
        pt1: Tuple[int, int],
        pt2: Tuple[int, int],
        color: Tuple[int, int, int] = COLOR_DASH_BG,
        radius: int = 12,
        thickness: int = -1,
    ) -> None:
        """
        Draw a rounded rectangle between pt1 (top-left) and pt2 (bottom-right)
        using arcs at the corners and filled rectangles/ellipses in between.
        `thickness = -1` fills the shape; any positive value draws an outline.
        """
        x1, y1 = pt1
        x2, y2 = pt2
        radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))

        if thickness < 0:
            cv2.rectangle(frame, (x1 + radius, y1), (x2 - radius, y2), color, -1, cv2.LINE_AA)
            cv2.rectangle(frame, (x1, y1 + radius), (x2, y2 - radius), color, -1, cv2.LINE_AA)
            cv2.ellipse(frame, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, -1, cv2.LINE_AA)
            cv2.ellipse(frame, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, -1, cv2.LINE_AA)
            cv2.ellipse(frame, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, -1, cv2.LINE_AA)
            cv2.ellipse(frame, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, -1, cv2.LINE_AA)
        else:
            cv2.line(frame, (x1 + radius, y1), (x2 - radius, y1), color, thickness, cv2.LINE_AA)
            cv2.line(frame, (x1 + radius, y2), (x2 - radius, y2), color, thickness, cv2.LINE_AA)
            cv2.line(frame, (x1, y1 + radius), (x1, y2 - radius), color, thickness, cv2.LINE_AA)
            cv2.line(frame, (x2, y1 + radius), (x2, y2 - radius), color, thickness, cv2.LINE_AA)
            cv2.ellipse(frame, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness, cv2.LINE_AA)
            cv2.ellipse(frame, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness, cv2.LINE_AA)
            cv2.ellipse(frame, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness, cv2.LINE_AA)
            cv2.ellipse(frame, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness, cv2.LINE_AA)