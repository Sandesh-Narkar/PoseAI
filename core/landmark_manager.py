"""
landmark_manager.py
--------------------
Central utility for extracting and working with MediaPipe Pose
landmarks. Provides readable constants, safe accessors, and
reusable helper methods for arms, legs, and body-center
calculations used across all workout modules.

PoseAI Project
"""

from typing import List, Dict, Tuple, Optional, Sequence


class LandmarkManager:
    """
    Central manager for MediaPipe Pose landmarks.

    Responsible for:
        - Extracting raw landmarks from MediaPipe results.
        - Providing safe, readable access to individual points.
        - Providing higher-level helpers (arms, legs, body center)
          used by workout classes instead of raw indices.
    """

    # -----------------------------
    # MediaPipe Landmark IDs (0-32)
    # -----------------------------
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

    # Default fallback point when data is missing/incomplete.
    _DEFAULT_POINT: Tuple[float, float] = (0.0, 0.0)
    _DEFAULT_VISIBILITY: float = 0.0

    # -----------------------------
    # Extract all landmarks
    # -----------------------------
    def get_landmarks(self, result) -> List[Dict]:
        """
        Extract all 33 pose landmarks from a MediaPipe Pose
        Landmarker result.

        Args:
            result: MediaPipe Pose Landmarker result object.

        Returns:
            List of dicts, each containing:
                id, x, y, z, visibility
            Returns an empty list if no pose was detected.
        """
        landmarks: List[Dict] = []

        if not result or not getattr(result, "pose_landmarks", None):
            return landmarks

        try:
            pose = result.pose_landmarks[0]
        except (IndexError, TypeError):
            return landmarks

        for index, landmark in enumerate(pose):
            landmarks.append({
                "id": index,
                "x": getattr(landmark, "x", 0.0),
                "y": getattr(landmark, "y", 0.0),
                "z": getattr(landmark, "z", 0.0),
                "visibility": getattr(landmark, "visibility", 0.0),
            })

        return landmarks

    # -----------------------------
    # Safe point accessor
    # -----------------------------
    def get_point(
        self,
        landmarks: Sequence[Dict],
        index: int
    ) -> Tuple[float, float]:
        """
        Safely return the (x, y) tuple for a given landmark index.

        Args:
            landmarks: List of landmark dicts.
            index: Landmark index to retrieve.

        Returns:
            (x, y) tuple. Returns (0.0, 0.0) if data is missing
            or the index is out of range.
        """
        if not landmarks or index < 0 or index >= len(landmarks):
            return self._DEFAULT_POINT

        point = landmarks[index]

        try:
            return (point["x"], point["y"])
        except (KeyError, TypeError):
            return self._DEFAULT_POINT

    # -----------------------------
    # Internal: safe visibility accessor
    # -----------------------------
    def _get_visibility(
        self,
        landmarks: Sequence[Dict],
        index: int
    ) -> float:
        """Safely return the visibility score for a landmark index."""
        if not landmarks or index < 0 or index >= len(landmarks):
            return self._DEFAULT_VISIBILITY

        try:
            return landmarks[index].get("visibility", 0.0)
        except (AttributeError, TypeError):
            return self._DEFAULT_VISIBILITY

    # -----------------------------
    # Average visibility
    # -----------------------------
    def get_average_visibility(
        self,
        landmarks: Sequence[Dict],
        indices: Sequence[int]
    ) -> float:
        """
        Calculate the average visibility score across a set of
        landmark indices.

        Args:
            landmarks: List of landmark dicts.
            indices: Landmark indices to average.

        Returns:
            Average visibility (0.0 - 1.0). Returns 0.0 if
            landmarks or indices are missing/empty.
        """
        if not landmarks or not indices:
            return self._DEFAULT_VISIBILITY

        scores = [self._get_visibility(landmarks, i) for i in indices]

        if not scores:
            return self._DEFAULT_VISIBILITY

        return sum(scores) / len(scores)

    # -----------------------------
    # Visibility checks
    # -----------------------------
    def is_landmark_visible(
        self,
        landmarks: Sequence[Dict],
        index: int,
        threshold: float = 0.5
    ) -> bool:
        """
        Check whether a single landmark meets the visibility
        threshold.

        Args:
            landmarks: List of landmark dicts.
            index: Landmark index to check.
            threshold: Minimum visibility required (default 0.5).

        Returns:
            True if visibility >= threshold, otherwise False.
        """
        return self._get_visibility(landmarks, index) >= threshold

    def is_full_body_visible(
        self,
        landmarks: Sequence[Dict],
        threshold: float = 0.5
    ) -> bool:
        """
        Check whether all major joints (shoulders, hips, knees,
        ankles) meet the visibility threshold.

        Args:
            landmarks: List of landmark dicts.
            threshold: Minimum visibility required per joint.

        Returns:
            True only if every major joint is visible, otherwise
            False. Returns False if landmarks are empty.
        """
        if not landmarks:
            return False

        major_joints = (
            self.LEFT_SHOULDER, self.RIGHT_SHOULDER,
            self.LEFT_HIP, self.RIGHT_HIP,
            self.LEFT_KNEE, self.RIGHT_KNEE,
            self.LEFT_ANKLE, self.RIGHT_ANKLE,
        )

        return all(
            self.is_landmark_visible(landmarks, joint, threshold)
            for joint in major_joints
        )

    # -----------------------------
    # LEFT ARM
    # -----------------------------
    def get_left_arm(self, landmarks: Sequence[Dict]) -> Dict:
        """
        Return left arm keypoints plus average visibility.

        Returns:
            {
                "shoulder": (x, y),
                "elbow": (x, y),
                "wrist": (x, y),
                "visibility": float
            }
        """
        indices = (self.LEFT_SHOULDER, self.LEFT_ELBOW, self.LEFT_WRIST)

        return {
            "shoulder": self.get_point(landmarks, self.LEFT_SHOULDER),
            "elbow": self.get_point(landmarks, self.LEFT_ELBOW),
            "wrist": self.get_point(landmarks, self.LEFT_WRIST),
            "visibility": self.get_average_visibility(landmarks, indices),
        }

    # -----------------------------
    # RIGHT ARM
    # -----------------------------
    def get_right_arm(self, landmarks: Sequence[Dict]) -> Dict:
        """
        Return right arm keypoints plus average visibility.

        Returns:
            {
                "shoulder": (x, y),
                "elbow": (x, y),
                "wrist": (x, y),
                "visibility": float
            }
        """
        indices = (self.RIGHT_SHOULDER, self.RIGHT_ELBOW, self.RIGHT_WRIST)

        return {
            "shoulder": self.get_point(landmarks, self.RIGHT_SHOULDER),
            "elbow": self.get_point(landmarks, self.RIGHT_ELBOW),
            "wrist": self.get_point(landmarks, self.RIGHT_WRIST),
            "visibility": self.get_average_visibility(landmarks, indices),
        }

    # -----------------------------
    # BEST ARM (auto-select)
    # -----------------------------
    def get_best_arm(self, landmarks: Sequence[Dict]) -> Dict:
        """
        Compare left and right arm average visibility and return
        whichever arm is more reliably visible.

        This allows workouts (e.g. bicep curls) to work correctly
        even if the user is angled toward the camera and only one
        arm is clearly tracked.

        Returns:
            Same structure as get_left_arm() / get_right_arm().
        """
        left_arm = self.get_left_arm(landmarks)
        right_arm = self.get_right_arm(landmarks)

        if right_arm["visibility"] > left_arm["visibility"]:
            return right_arm

        return left_arm

    # -----------------------------
    # LEFT LEG
    # -----------------------------
    def get_left_leg(self, landmarks: Sequence[Dict]) -> Dict:
        """
        Return left leg keypoints plus average visibility.

        Returns:
            {
                "hip": (x, y),
                "knee": (x, y),
                "ankle": (x, y),
                "visibility": float
            }
        """
        indices = (self.LEFT_HIP, self.LEFT_KNEE, self.LEFT_ANKLE)

        return {
            "hip": self.get_point(landmarks, self.LEFT_HIP),
            "knee": self.get_point(landmarks, self.LEFT_KNEE),
            "ankle": self.get_point(landmarks, self.LEFT_ANKLE),
            "visibility": self.get_average_visibility(landmarks, indices),
        }

    # -----------------------------
    # RIGHT LEG
    # -----------------------------
    def get_right_leg(self, landmarks: Sequence[Dict]) -> Dict:
        """
        Return right leg keypoints plus average visibility.

        Returns:
            {
                "hip": (x, y),
                "knee": (x, y),
                "ankle": (x, y),
                "visibility": float
            }
        """
        indices = (self.RIGHT_HIP, self.RIGHT_KNEE, self.RIGHT_ANKLE)

        return {
            "hip": self.get_point(landmarks, self.RIGHT_HIP),
            "knee": self.get_point(landmarks, self.RIGHT_KNEE),
            "ankle": self.get_point(landmarks, self.RIGHT_ANKLE),
            "visibility": self.get_average_visibility(landmarks, indices),
        }

    # -----------------------------
    # BEST LEG (auto-select)
    # -----------------------------
    def get_best_leg(self, landmarks: Sequence[Dict]) -> Dict:
        """
        Compare left and right leg average visibility and return
        whichever leg is more reliably visible.

        Useful for squats/lunges when the user is angled sideways
        to the camera.

        Returns:
            Same structure as get_left_leg() / get_right_leg().
        """
        left_leg = self.get_left_leg(landmarks)
        right_leg = self.get_right_leg(landmarks)

        if right_leg["visibility"] > left_leg["visibility"]:
            return right_leg

        return left_leg

    # -----------------------------
    # BODY CENTER
    # -----------------------------
    def get_body_center(self, landmarks: Sequence[Dict]) -> Tuple[float, float]:
        """
        Calculate the approximate center of the body using the
        midpoint of both shoulders and both hips.

        Returns:
            (x, y) tuple representing the body center.
            Returns (0.0, 0.0) if landmarks are missing.
        """
        if not landmarks:
            return self._DEFAULT_POINT

        left_shoulder = self.get_point(landmarks, self.LEFT_SHOULDER)
        right_shoulder = self.get_point(landmarks, self.RIGHT_SHOULDER)
        left_hip = self.get_point(landmarks, self.LEFT_HIP)
        right_hip = self.get_point(landmarks, self.RIGHT_HIP)

        points = (left_shoulder, right_shoulder, left_hip, right_hip)

        center_x = sum(p[0] for p in points) / len(points)
        center_y = sum(p[1] for p in points) / len(points)

        return (center_x, center_y)