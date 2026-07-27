"""
core/landmark_smoother.py
==========================

Temporal stabilization layer for PoseAI - Real-Time AI Fitness Trainer.

Sits between LandmarkManager and AngleCalculator in the processing
pipeline:

    Camera -> PoseDetector -> LandmarkManager -> LandmarkSmoother
           -> AngleCalculator -> WorkoutManager

Applies a VELOCITY-ADAPTIVE Exponential Moving Average (EMA) filter to
each of the 33 pose landmarks. Unlike a fixed-alpha EMA, the smoothing
strength is recalculated every frame, per landmark, based on how fast
that landmark is currently moving:

    - Slow / stationary landmark  -> LOW alpha  -> heavier smoothing
      (removes jitter when the joint is basically still, e.g. the
      bottom of a squat hold).
    - Fast-moving landmark        -> HIGH alpha -> lighter smoothing
      (tracks real motion almost immediately, e.g. a fast bicep curl
      or a burpee jump), eliminating the "lag behind the body" and
      "sluggish wrist" feeling of a fixed-alpha filter.

This is a lightweight version of the "1-Euro Filter" concept used in
professional motion-tracking pipelines: cutoff (here, alpha) scales
with the estimated speed of the signal instead of staying constant.

The public data format is preserved exactly so no changes are required
in AngleCalculator, WorkoutManager, the individual workout classes, or
main.py:

    {"id": int, "x": float, "y": float, "z": float, "visibility": float}

Author: PoseAI Engineering Team
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

# A single landmark, as produced by LandmarkManager.
Landmark = Dict[str, float]
LandmarkList = List[Landmark]

# Total number of MediaPipe Pose landmarks expected per frame.
TOTAL_LANDMARKS = 33

# Required keys for a well-formed landmark dictionary.
_REQUIRED_KEYS = ("id", "x", "y", "z", "visibility")


class LandmarkSmoother:
    """
    Stabilizes a stream of per-frame pose landmarks using a
    velocity-adaptive Exponential Moving Average filter with
    visibility-aware gating.

    The smoother is frame-independent: it holds only the previous
    frame's smoothed landmarks as internal state and requires no
    knowledge of timestamps, FPS, or camera configuration. This keeps
    it trivially reusable and makes a future upgrade to a proper
    Kalman filter (which would replace the internal state and the
    `smooth_point` implementation only) a drop-in change with no
    impact on the rest of the pipeline.
    """

    #: Base/default EMA smoothing factor. This is the user-tunable
    #: "center point" of the adaptive range: raising it (via
    #: set_alpha) biases the whole filter toward faster response,
    #: lowering it biases toward heavier smoothing. The *effective*
    #: per-frame alpha still varies around this value based on how
    #: fast each landmark is moving (see MIN/MAX_ALPHA_OFFSET below).
    DEFAULT_ALPHA: float = 0.6

    #: Landmarks with visibility below this threshold are considered
    #: unreliable and are not used to update the smoothed estimate.
    DEFAULT_VISIBILITY_THRESHOLD: float = 0.5

    # ------------------------------------------------------------------ #
    # ADAPTIVE-ALPHA TUNING CONSTANTS
    # ------------------------------------------------------------------ #

    #: How far below `self.alpha` the effective alpha is allowed to
    #: drop when a landmark is nearly stationary. A larger offset means
    #: stronger jitter removal during holds (e.g. bottom of a squat,
    #: top of a shoulder press) at the cost of more smoothing lag if
    #: the person then moves suddenly - which is fine because the
    #: velocity term below reacts within a single frame.
    MIN_ALPHA_OFFSET: float = 0.35

    #: How far above `self.alpha` the effective alpha is allowed to
    #: rise when a landmark is moving quickly. A larger offset means
    #: faster-moving joints (wrists during a curl, ankles during a
    #: jumping jack) are tracked almost immediately instead of lagging.
    MAX_ALPHA_OFFSET: float = 0.35

    #: Normalized-coordinate displacement (MediaPipe landmarks are in
    #: the 0.0-1.0 range) per frame above which a landmark is treated
    #: as "fast" and gets the maximum alpha. Tuned empirically for
    #: webcam framerates (~24-30 FPS): a wrist during a brisk curl or
    #: a jumping-jack limb typically moves ~0.05-0.10 per frame, so
    #: 0.06 saturates responsiveness right in that range without
    #: over-reacting to normal detector noise (~0.002-0.01/frame).
    VELOCITY_SATURATION: float = 0.06

    #: Minimum world-clamp for effective alpha, regardless of tuning
    #: above/below, so the filter never fully freezes (0.0 would mean
    #: "never update") or fully passes through raw noise (1.0 would
    #: mean "no smoothing at all").
    _ALPHA_FLOOR: float = 0.05
    _ALPHA_CEIL: float = 0.98

    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        visibility_threshold: float = DEFAULT_VISIBILITY_THRESHOLD,
    ) -> None:
        """
        Initialize the smoother.

        Args:
            alpha: Configurable base EMA smoothing factor in the range
                (0.0, 1.0]. Defaults to 0.6. Acts as the center point
                of the velocity-adaptive alpha range (see class docs).
            visibility_threshold: Minimum visibility score for a
                landmark to be trusted and blended into the EMA.
                Landmarks below this threshold reuse the previous
                valid value instead. Defaults to 0.5.
        """
        self.alpha: float = self._clamp_alpha(alpha)
        self.visibility_threshold: float = visibility_threshold

        # Internal state: the last smoothed landmark list, keyed by
        # landmark id for O(1) lookup regardless of input ordering.
        self._previous: Optional[Dict[int, Landmark]] = None

    # ------------------------------------------------------------------ #
    # CONFIGURATION HELPERS
    # ------------------------------------------------------------------ #

    @staticmethod
    def _clamp_alpha(alpha: float) -> float:
        """Keep alpha within a safe, numerically valid (0.0, 1.0] range."""
        if alpha <= 0.0:
            return 0.01
        if alpha > 1.0:
            return 1.0
        return alpha

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        """Generic clamp used by the velocity-to-alpha mapping."""
        if value < lo:
            return lo
        if value > hi:
            return hi
        return value

    def set_alpha(self, alpha: float) -> None:
        """Update the base smoothing factor at runtime without resetting state."""
        self.alpha = self._clamp_alpha(alpha)

    def set_visibility_threshold(self, threshold: float) -> None:
        """Update the minimum visibility required to trust a landmark."""
        self.visibility_threshold = threshold

    # ------------------------------------------------------------------ #
    # STATE MANAGEMENT
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """
        Clear all internal state.

        Call this whenever tracking is intentionally interrupted (e.g.
        the subject leaves the frame, a new workout session starts, or
        the camera source changes) so stale positions from a previous
        session are never blended into new landmarks.
        """
        self._previous = None

    # ------------------------------------------------------------------ #
    # VALIDATION
    # ------------------------------------------------------------------ #

    def is_valid(self, landmark: Landmark) -> bool:
        """
        Check whether a landmark is well-formed and sufficiently
        confident to be trusted for smoothing.

        Args:
            landmark: A single landmark dictionary.

        Returns:
            True if the landmark has all required keys and a
            visibility score at or above the configured threshold.
        """
        if not isinstance(landmark, dict):
            return False
        if not all(key in landmark for key in _REQUIRED_KEYS):
            return False

        visibility = landmark.get("visibility", 0.0)
        try:
            return float(visibility) >= self.visibility_threshold
        except (TypeError, ValueError):
            return False

    # ------------------------------------------------------------------ #
    # ADAPTIVE ALPHA
    # ------------------------------------------------------------------ #

    def _compute_adaptive_alpha(self, previous: Landmark, current: Landmark) -> float:
        """
        Compute the effective EMA alpha for this landmark, this frame,
        based on how far it moved since the last smoothed frame.

        This is the core latency fix: a fixed alpha forces a tradeoff
        between "smooth but laggy" and "fast but jittery" for every
        situation. By measuring per-frame displacement (a cheap proxy
        for velocity, since we don't need true units - only relative
        speed) and scaling alpha with it, slow/held positions get
        heavy smoothing while fast reps get near-instant response,
        without needing two separate filters or extra frame buffering.

        Args:
            previous: The previously smoothed landmark for this id.
            current: The newly observed (raw) landmark.

        Returns:
            An alpha value in [_ALPHA_FLOOR, _ALPHA_CEIL] to use for
            blending this specific point on this specific frame.
        """
        dx = current["x"] - previous["x"]
        dy = current["y"] - previous["y"]

        # Euclidean displacement in normalized coordinate space. z is
        # intentionally excluded - MediaPipe's z estimate is noisier
        # and less reliable than x/y, so letting it drive alpha would
        # inject jitter-driven responsiveness rather than real-motion
        # responsiveness.
        speed = math.hypot(dx, dy)

        # Normalize speed into a 0.0-1.0 "how fast is this" ratio,
        # saturating at VELOCITY_SATURATION so an unusually large
        # single-frame jump (e.g. a brief mis-detection) doesn't push
        # alpha further than the configured max.
        speed_ratio = self._clamp(speed / self.VELOCITY_SATURATION, 0.0, 1.0)

        # Interpolate alpha around the user-configured base value:
        # slow motion pulls alpha down toward (alpha - MIN_ALPHA_OFFSET),
        # fast motion pushes alpha up toward (alpha + MAX_ALPHA_OFFSET).
        min_alpha = self._clamp(self.alpha - self.MIN_ALPHA_OFFSET, self._ALPHA_FLOOR, self._ALPHA_CEIL)
        max_alpha = self._clamp(self.alpha + self.MAX_ALPHA_OFFSET, self._ALPHA_FLOOR, self._ALPHA_CEIL)

        return min_alpha + (max_alpha - min_alpha) * speed_ratio

    # ------------------------------------------------------------------ #
    # CORE SMOOTHING
    # ------------------------------------------------------------------ #

    def smooth_point(self, previous: Landmark, current: Landmark) -> Landmark:
        """
        Blend a single previous/current landmark pair using a
        velocity-adaptive EMA.

        Args:
            previous: The previously smoothed landmark.
            current: The newly observed (raw) landmark.

        Returns:
            A new landmark dictionary with EMA-smoothed x, y, z and
            the current frame's visibility score.
        """
        alpha = self._compute_adaptive_alpha(previous, current)
        inverse_alpha = 1.0 - alpha

        return {
            "id": current["id"],
            "x": alpha * current["x"] + inverse_alpha * previous["x"],
            "y": alpha * current["y"] + inverse_alpha * previous["y"],
            # z uses the same adaptive alpha as x/y for consistency,
            # even though it wasn't part of the speed calculation -
            # this keeps depth smoothing in sync with planar smoothing
            # instead of drifting out of phase with it.
            "z": alpha * current["z"] + inverse_alpha * previous["z"],
            "visibility": current["visibility"],
        }

    def smooth(self, landmarks: LandmarkList) -> LandmarkList:
        """
        Smooth an entire frame of landmarks against the previously
        stored smoothed frame.

        Behavior:
            - Empty input -> returns an empty list.
            - No previous frame stored -> returns the current
              landmarks unchanged (as a new list, never mutating the
              input) and stores them as the initial smoothing state.
            - Low-visibility / temporarily-lost landmarks are never
              blended; the last known valid (smoothed) landmark is
              reused in their place so downstream angle calculations
              never see a jump caused by a momentarily occluded joint
              - and critically, this happens on the SAME frame with no
              extra buffering delay.
            - Landmarks that ARE visible get an alpha computed fresh
              every frame from their current speed, so fast reps are
              tracked immediately while held positions stay jitter-free.
            - The original input list and its dictionaries are never
              mutated; a brand new list of new dictionaries is always
              returned.

        Args:
            landmarks: The current frame's landmark list, as produced
                by LandmarkManager.

        Returns:
            A new list of smoothed landmark dictionaries in the same
            {"id", "x", "y", "z", "visibility"} format.
        """
        if not landmarks:
            return []

        # First frame ever seen (or state was reset): nothing to blend
        # against yet, so pass the current frame through untouched but
        # establish it as the smoothing baseline for subsequent frames.
        if self._previous is None:
            initial = [dict(landmark) for landmark in landmarks]
            self._previous = {lm["id"]: dict(lm) for lm in initial}
            return initial

        smoothed_output: LandmarkList = []
        updated_state: Dict[int, Landmark] = {}

        for current in landmarks:
            landmark_id = current.get("id")
            previous = self._previous.get(landmark_id)

            if previous is None:
                # Never seen this id before (unexpected but handled
                # safely): treat it as a fresh baseline point.
                result = dict(current)
            elif self.is_valid(current):
                # Trusted observation: blend into the running estimate
                # using this frame's velocity-adaptive alpha.
                result = self.smooth_point(previous, current)
            else:
                # Unreliable/occluded observation: hold the last valid
                # position immediately (no wait-and-see delay) but
                # surface the current (low) visibility so the rest of
                # the pipeline still knows confidence is low.
                result = dict(previous)
                result["visibility"] = current.get("visibility", previous["visibility"])

            smoothed_output.append(result)
            updated_state[landmark_id] = dict(result)

        self._previous = updated_state
        return smoothed_output