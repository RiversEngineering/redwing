"""Example 17 — Navigate toward a specific AprilTag.

The robot searches for a target tag (TARGET_ID). When found, two PID
controllers work simultaneously:

  - Lateral PID:  steers left/right to centre the tag horizontally
  - Depth PID:    drives forward/backward to reach STOP_DISTANCE_CM

When no tag is visible the robot slowly rotates to search. Use
robot.plot() on the dashboard to tune the PID gains live.

Hardware
--------
- Left motor controller  → D0
- Right motor controller → D1
- Pi camera or USB webcam

Setup
-----
Print a tag36h11 marker, set TARGET_ID to match its number, and measure
its physical side length for TAG_SIZE_CM. Tune FOCAL_PX once per camera
as described in 16_apriltag_distance.py.
"""

import cv2
import numpy as np

from redwing import Robot

# --- Configuration ---
TARGET_ID        = 0       # tag ID to approach
TAG_SIZE_CM      = 10.0    # physical side length in cm
FOCAL_PX         = 600     # camera focal length in pixels
STOP_DISTANCE_CM = 30.0    # desired stopping distance
FRAME_WIDTH      = 640

# --- Lateral (steering) PID ---
LAT_KP = 0.08   # proportional gain
LAT_KI = 0.002  # integral gain
LAT_KD = 0.01   # derivative gain

# --- Depth (forward/backward) PID ---
DEPTH_KP = 0.8
DEPTH_KI = 0.05
DEPTH_KD = 0.1

MAX_SPEED = 70   # % power cap for any motor

# --- Setup ---
robot = Robot()

left  = robot.D0.motor()
right = robot.D1.motor()

robot.start()

dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
detector   = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())

# PID state
lat_integral   = 0.0
lat_prev_err   = 0.0
depth_integral = 0.0
depth_prev_err = 0.0
search_dir     = 1          # 1 = rotate right, -1 = rotate left

robot.log("Searching for tag…")

while True:
    frame = cam_frame = robot.camera.read()

    corners, ids, _ = detector.detectMarkers(frame)

    target_corners = None
    if ids is not None:
        for i, tag_id in enumerate(ids.flatten()):
            if tag_id == TARGET_ID:
                target_corners = corners[i][0]
                break

    annotated = cv2.aruco.drawDetectedMarkers(frame.copy(), corners, ids) \
                if ids is not None else frame.copy()

    if target_corners is None:
        # --- Search: rotate slowly ---
        lat_integral = lat_prev_err = depth_integral = depth_prev_err = 0.0
        left.set_power(20 * search_dir)
        right.set_power(-20 * search_dir)
        robot.log("Searching…")

    else:
        # --- Lateral error: pixels from image centre ---
        cx          = target_corners[:, 0].mean()
        lat_err     = cx - FRAME_WIDTH / 2        # +ve = tag to the right

        lat_integral  += lat_err
        lat_integral   = max(-300, min(300, lat_integral))   # anti-windup
        lat_deriv      = lat_err - lat_prev_err
        lat_prev_err   = lat_err
        lat_out        = LAT_KP * lat_err + LAT_KI * lat_integral + LAT_KD * lat_deriv

        # --- Depth error: cm from target distance ---
        top_w       = np.linalg.norm(target_corners[1] - target_corners[0])
        bottom_w    = np.linalg.norm(target_corners[2] - target_corners[3])
        pixel_w     = (top_w + bottom_w) / 2
        distance_cm = (TAG_SIZE_CM * FOCAL_PX) / max(1, pixel_w)
        depth_err   = distance_cm - STOP_DISTANCE_CM   # +ve = too far → drive forward

        depth_integral += depth_err
        depth_integral  = max(-200, min(200, depth_integral))
        depth_deriv     = depth_err - depth_prev_err
        depth_prev_err  = depth_err
        depth_out       = DEPTH_KP * depth_err + DEPTH_KI * depth_integral + DEPTH_KD * depth_deriv

        # Combine: depth sets forward speed, lateral steers
        l_power = max(-MAX_SPEED, min(MAX_SPEED,  depth_out - lat_out))
        r_power = max(-MAX_SPEED, min(MAX_SPEED,  depth_out + lat_out))

        left.set_power(l_power)
        right.set_power(r_power)

        # Annotate frame
        cv2.putText(
            annotated,
            f"{distance_cm:.0f} cm  err={lat_err:+.0f}px",
            (int(target_corners[0][0]), int(target_corners[0][1]) - 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2,
        )

        robot.plot("distance_cm", distance_cm)
        robot.plot("lat_err_px",  lat_err)
        robot.log(f"Tag {TARGET_ID}: {distance_cm:.1f} cm  lateral={lat_err:+.0f} px")

    robot.camera.show(annotated)
    robot.sleep(0.05)
