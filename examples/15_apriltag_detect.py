"""Example 15 — Detect AprilTags with the camera.

Reads the camera, finds all AprilTag 36h11 markers in the frame, draws
a bounding box and ID number on each one, and sends the annotated frame
to the dashboard.

AprilTags are fiducial markers — printed squares that the robot can
uniquely identify and locate. Each tag has a numeric ID encoded in its
pattern. Print tags from:
  https://github.com/AprilRobotics/apriltag-imgs/tree/master/tag36h11

Hardware
--------
- Pi camera or USB webcam (connected to Raspberry Pi)

No motors or Pico ports are needed for this example.
"""

import cv2
import numpy as np

from redwing import Robot

robot = Robot()
cam   = robot.camera

robot.start()

# Build the AprilTag detector once (reused every frame)
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
detector   = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())

while True:
    frame = cam.read()

    corners, ids, _ = detector.detectMarkers(frame)

    if ids is not None:
        # Draw bounding boxes on a copy of the frame
        annotated = cv2.aruco.drawDetectedMarkers(frame.copy(), corners, ids)

        for i, tag_id in enumerate(ids.flatten()):
            # Compute the tag's center from its four corners
            pts = corners[i][0]
            cx  = int(pts[:, 0].mean())
            cy  = int(pts[:, 1].mean())

            cv2.circle(annotated, (cx, cy), 5, (0, 255, 0), -1)
            cv2.putText(
                annotated, f"ID {tag_id}",
                (cx + 8, cy - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
            )

        robot.log(f"Detected tags: {ids.flatten().tolist()}")
        cam.show(annotated)
    else:
        cam.show(frame)

    robot.sleep(0.05)
