"""Camera access and dashboard display control."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # For type checkers only — not imported at runtime (see lazy loading below).
    import numpy as np


# ── Lazy OpenCV loading ─────────────────────────────────────────────────────
# OpenCV is imported on first camera use rather than at module load. Importing
# `cv2` costs ~200 MB of resident memory, and on a 2 GB Pi 4 the daemon already
# holds one copy for the live feed. Deferring the import here means a student
# program that never touches the camera (drive, sensors, lidar, gamepad, PID…)
# never loads a second copy — it only appears when vision code actually runs.
_OPENCV_THREADS = 2  # Cap OpenCV's internal thread pool. On a 4-core Pi this
                     # leaves cores free for the daemon's camera-feed loop, so
                     # a student's heavy vision work (e.g. AprilTag detection)
                     # can't starve the feed and make it stutter.
_cv2 = None


def _cv():
    """Import OpenCV on first use and cap its thread pool (once)."""
    global _cv2
    if _cv2 is None:
        import cv2
        cv2.setNumThreads(_OPENCV_THREADS)
        _cv2 = cv2
    return _cv2


class Camera:
    """Access the robot's webcam and control what appears on the dashboard.

    Example::

        # Show the raw camera feed on the dashboard
        robot.camera.show()

        # Read, process, and display a frame
        frame = robot.camera.read()
        # ... do OpenCV processing ...
        robot.camera.show(frame)

        # Color detection helper
        mask = robot.camera.color_mask(frame, "red")
    """

    def __init__(self, conn):
        self._conn = conn

    def read(self) -> np.ndarray:
        """Return the latest camera frame as a NumPy array (BGR, same as OpenCV).

        Returns an empty black frame if no camera is available.
        """
        import numpy as np
        cv2 = _cv()

        state = self._conn.get_all_state()
        frame_b64 = state.get("camera_frame")
        if not frame_b64:
            return np.zeros((480, 640, 3), dtype=np.uint8)
        raw = base64.b64decode(frame_b64)
        buf = np.frombuffer(raw, dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    def show(self, frame: np.ndarray | None = None):
        """Send a frame to the dashboard camera display.

        If ``frame`` is ``None``, the dashboard shows the raw camera feed.
        Pass a processed frame (e.g., with OpenCV annotations drawn on it)
        to display that instead.
        """
        if frame is None:
            self._conn.send_command(cmd="camera_show_raw")
            return
        cv2 = _cv()
        _, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        b64 = base64.b64encode(encoded.tobytes()).decode()
        self._conn.send_command(cmd="camera_show_frame", frame=b64)

    def color_mask(
        self,
        frame: np.ndarray,
        color: str,
    ) -> np.ndarray:
        """Return a binary mask highlighting pixels of the given color.

        ``color`` can be ``"red"``, ``"green"``, ``"blue"``, ``"yellow"``,
        or ``"orange"``.

        Example::

            frame = robot.camera.read()
            mask  = robot.camera.color_mask(frame, "red")
            area  = cv2.countNonZero(mask)
            if area > 500:
                robot.log("Red object detected!")
        """
        import numpy as np
        cv2 = _cv()

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        ranges = {
            "red":    [(0, 80, 80),   (10, 255, 255),  (160, 80, 80), (180, 255, 255)],
            "green":  [(40, 60, 60),  (90, 255, 255)],
            "blue":   [(100, 80, 80), (140, 255, 255)],
            "yellow": [(20, 100, 100),(35, 255, 255)],
            "orange": [(5, 100, 100), (20, 255, 255)],
        }

        if color not in ranges:
            raise ValueError(
                f"Unknown color '{color}'. "
                f"Choose from: {', '.join(ranges.keys())}"
            )

        bounds = ranges[color]
        if len(bounds) == 4:
            # Red wraps around the HSV hue circle — combine two ranges
            lo1 = np.array(bounds[0], dtype=np.uint8)
            hi1 = np.array(bounds[1], dtype=np.uint8)
            lo2 = np.array(bounds[2], dtype=np.uint8)
            hi2 = np.array(bounds[3], dtype=np.uint8)
            mask = cv2.inRange(hsv, lo1, hi1) | cv2.inRange(hsv, lo2, hi2)
        else:
            lo = np.array(bounds[0], dtype=np.uint8)
            hi = np.array(bounds[1], dtype=np.uint8)
            mask = cv2.inRange(hsv, lo, hi)

        kernel = np.ones((5, 5), np.uint8)
        return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    def find_largest_contour(self, mask: np.ndarray):
        """Return the centroid ``(x, y)`` and area of the largest blob in a mask.

        Returns ``(None, None, 0)`` if no blob is found.

        Example::

            mask = robot.camera.color_mask(frame, "blue")
            x, y, area = robot.camera.find_largest_contour(mask)
            if area > 500:
                robot.log(f"Blue blob at ({x}, {y}), area={area}")
        """
        cv2 = _cv()

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, None, 0
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        m = cv2.moments(largest)
        if m["m00"] == 0:
            return None, None, 0
        cx = int(m["m10"] / m["m00"])
        cy = int(m["m01"] / m["m00"])
        return cx, cy, int(area)
