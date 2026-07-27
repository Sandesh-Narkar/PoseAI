"""
camera.py
----------

This module is responsible for:
- Opening the webcam
- Reading video frames
- Flipping frames horizontally
- Releasing the webcam safely

It does NOT perform:
- Pose detection
- Angle calculations
- Exercise tracking
"""

import cv2


class Camera:
    """Handles all webcam operations."""

    def __init__(self, camera_index=0):
        """
        Initialize the camera object.

        Args:
            camera_index (int):
                Camera device index.
                Default is 0 (built-in webcam).
        """
        self.camera_index = camera_index
        self.cap = None

    def start(self):
        """
        Open the webcam.

        Raises:
            RuntimeError:
                If the webcam cannot be opened.
        """
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            raise RuntimeError("Failed to open webcam.")

    def read_frame(self):
        """
        Read one frame from the webcam.

        Returns:
            frame (numpy.ndarray):
                Mirrored webcam frame.

        Returns None if frame capture fails.
        """
        if self.cap is None:
            return None

        success, frame = self.cap.read()

        if not success:
            return None

        # Mirror the frame for a natural user experience
        frame = cv2.flip(frame, 1)

        return frame

    def is_open(self):
        """
        Check whether the webcam is open.

        Returns:
            bool
        """
        return self.cap is not None and self.cap.isOpened()

    def release(self):
        """
        Release the webcam safely.
        """
        if self.cap is not None:
            self.cap.release()
            self.cap = None