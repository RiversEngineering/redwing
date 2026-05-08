"""Example 6 — Camera color tracking.

Finds a colored object in the camera frame and steers toward it.

The camera image is 640×480 pixels. The center column is x=320.
If the object is to the left of center, we turn left; to the right, right.

Hardware needed:
  Port 1: left motor
  Port 2: right motor
  USB webcam connected to the Raspberry Pi
"""

import redwing

robot = redwing.Robot()

left  = robot.D0.motor()
right = robot.D1.motor()

right.inverted = True

TRACK_COLOR = "red"      # "red", "green", "blue", "yellow", or "orange"
BASE_SPEED  = 40         # forward speed while tracking
TURN_GAIN   = 0.15       # how aggressively to steer (0.0 – 0.5)
MIN_AREA    = 500        # ignore blobs smaller than this (pixels²)

IMAGE_WIDTH = 640
CENTER_X    = IMAGE_WIDTH // 2

robot.log(f"Looking for {TRACK_COLOR} objects. Press Ctrl+C to stop.")

while True:
    frame = robot.camera.read()

    # Find the color blob
    mask          = robot.camera.color_mask(frame, TRACK_COLOR)
    obj_x, obj_y, area = robot.camera.find_largest_contour(mask)

    if area >= MIN_AREA:
        # Draw a circle on the detected object for the dashboard
        import cv2
        annotated = frame.copy()
        cv2.circle(annotated, (obj_x, obj_y), 20, (0, 255, 0), 3)
        cv2.line(annotated, (CENTER_X, 0), (CENTER_X, 480), (100, 100, 100), 1)
        robot.camera.show(annotated)

        # Steer: positive error = object is to the right → turn right
        error      = obj_x - CENTER_X
        correction = error * TURN_GAIN

        left.speed  = BASE_SPEED + correction
        right.speed = BASE_SPEED - correction

        robot.log(f"Tracking! x={obj_x}, area={area}, correction={correction:.1f}")
    else:
        # Lost the object — stop and show the raw frame
        robot.stop()
        robot.camera.show()
        robot.log("No object found. Waiting...")

    robot.sleep(0.05)   # ~20 fps control loop
