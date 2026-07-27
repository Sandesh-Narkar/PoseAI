"""
pose_detector.py
----------------
Loads the MediaPipe Pose Landmarker model
and performs pose detection.
"""

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class PoseDetector:

    def __init__(self, model_path):

        base_options = python.BaseOptions(
            model_asset_path=model_path
        )

        options = vision.PoseLandmarkerOptions(
            base_options=base_options,

            # VIDEO mode enables MediaPipe's internal frame-to-frame
            # tracking (as opposed to IMAGE mode, which re-detects from
            # scratch every call). This is what keeps the skeleton from
            # jittering/re-snapping on every frame and is essential for
            # smooth real-time exercise tracking.
            running_mode=vision.RunningMode.VIDEO,

            # We only ever track a single person doing the workout.
            # Limiting to 1 pose avoids wasted compute on background
            # people and prevents the detector from occasionally
            # locking onto a second body in frame.
            num_poses=1,

            # Detection confidence: how confident the model must be
            # that a human pose exists in the frame before it commits
            # to landmarks at all. 0.5 is too permissive for fast
            # exercises like burpees/jumping jacks - it lets in noisy,
            # low-confidence detections that cause wrist/elbow drift.
            # Raising this filters out weak initial detections while
            # still detecting reliably under normal lighting.
            min_pose_detection_confidence=0.6,

            # Presence confidence: how confident the model must be that
            # the pose is STILL present in the current frame once
            # tracking has locked on. Raising this slightly helps the
            # detector let go faster during real occlusion (e.g. arm
            # crossing the body in crossover toe touches) rather than
            # hallucinating landmarks in the wrong place, which speeds
            # up correct re-acquisition afterward.
            min_pose_presence_confidence=0.6,

            # Tracking confidence: how confident the model must be to
            # continue tracking a landmark from the previous frame
            # instead of re-detecting it. Lower values make tracking
            # "stickier" (less jitter, better temporal smoothness) but
            # risk drift/lag during fast movement; higher values react
            # faster to real movement but can flicker. 0.5 sits at a
            # reasonable middle ground, but for fast, high-motion
            # exercises (burpees, jumping jacks) a slightly higher
            # value reduces the wrist/elbow instability you're seeing
            # without introducing noticeable lag on slow exercises.
            min_tracking_confidence=0.6
        )

        self.detector = vision.PoseLandmarker.create_from_options(options)

        # MediaPipe's VIDEO mode requires strictly increasing
        # timestamps. Tracking the last timestamp we sent lets us
        # silently correct any out-of-order or duplicate timestamp
        # coming from the caller instead of crashing mid-workout.
        self._last_timestamp_ms = -1

    def detect(self, mp_image, timestamp):
        """
        Run pose detection/tracking on a single video frame.

        Returns the MediaPipe detection result, or None if detection
        could not be performed on this frame (missing frame, invalid
        timestamp, or a transient detector error). Callers already
        treat a falsy/empty result as "no pose found this frame", so
        returning None here is safe and keeps the public API unchanged.
        """

        if mp_image is None:
            return None

        # Guard against invalid/non-integer timestamps from the
        # caller (e.g. a None or negative value slipping through).
        try:
            timestamp = int(timestamp)
        except (TypeError, ValueError):
            return None

        # VIDEO mode demands strictly increasing timestamps. If the
        # caller ever sends a timestamp that doesn't advance (clock
        # hiccup, dropped frame, restart), bump it forward by 1ms
        # instead of letting MediaPipe raise an exception.
        if timestamp <= self._last_timestamp_ms:
            timestamp = self._last_timestamp_ms + 1

        self._last_timestamp_ms = timestamp

        try:
            return self.detector.detect_for_video(
                mp_image,
                timestamp
            )
        except Exception:
            # A transient failure (e.g. brief occlusion causing an
            # internal tracking error) should not crash the app - the
            # caller already handles a None/empty result as "pose not
            # found this frame" and will recover on the next frame.
            return None

    def close(self):
        self.detector.close()