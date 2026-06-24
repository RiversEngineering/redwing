"""Example 16 — Estimate distance to an AprilTag.

Uses the pin-hole camera model to estimate how far away a tag is,
without needing full camera calibration.

The idea: if you know the tag's real width (TAG_SIZE_CM) and how wide
it appears in pixels (pixel_width), you can recover the distance:

    distance = (TAG_SIZE_CM × focal_length_px) / pixel_width

FOCAL_PX is the camera's focal length in pixels. The default (600) is
a reasonable estimate for a 70°-FOV webcam at 640×480. To calibrate it
precisely, hold a tag at a known distance D_cm and measure pixel_width,
then compute: FOCAL_PX = pixel_width × D_cm / TAG_SIZE_CM.

Hardware
--------
- Pi camera or USB webcam

No motors needed. Values are logged to the dashboard.
"""

import cv2
import numpy as np

from redwing import Robot

TAG_SIZE_CM = 10.0   # physical side length of the printed tag in cm
FOCAL_PX    = 600    # camera focal length in pixels (see note above)
TARGET_ID   = 0      # which tag ID to track (or None to track any)

FRAME_WIDTH = 640

robot = Robot()
cam   = robot.camera

robot.start()

dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
detector   = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())

while True:
    frame = cam.read()

    corners, ids, _ = detector.detectMarkers(frame)

    if ids is not None:
        annotated = cv2.aruco.drawDetectedMarkers(frame.copy(), corners, ids)

        for i, tag_id in enumerate(ids.flatten()):
            if TARGET_ID is not None and tag_id != TARGET_ID:
                continue

            pts = corners[i][0]   # shape (4, 2): top-left, top-right, bottom-right, bottom-left

            # Average the top and bottom edge widths for a robust pixel_width
            top_w    = np.linalg.norm(pts[1] - pts[0])
            bottom_w = np.linalg.norm(pts[2] - pts[3])
            pixel_width = (top_w + bottom_w) / 2

            if pixel_width < 1:
                continue

            distance_cm = (TAG_SIZE_CM * FOCAL_PX) / pixel_width

            # Horizontal offset from image center (+ve = tag is to the right)
            cx = pts[:, 0].mean()
            lateral_px = cx - FRAME_WIDTH / 2

            cv2.putText(
                annotated,
                f"ID {tag_id}  {distance_cm:.0f} cm",
                (int(pts[0][0]), int(pts[0][1]) - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2,
            )

            robot.log(
                f"Tag {tag_id}: distance={distance_cm:.1f} cm  "
                f"lateral={lateral_px:+.0f} px"
            )
            robot.plot("distance_cm", distance_cm)
            robot.plot("lateral_px",  lateral_px)

        cam.show(annotated)
    else:
        cam.show(frame)

    robot.sleep(0.05)
