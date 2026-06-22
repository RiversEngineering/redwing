"""Example 12 — Camera color tracking with servo pan.

Finds the largest blob of a chosen color in the camera image and pans
a servo so that the robot's "head" always points at it.

The camera image is 640×480 pixels. A P-controller converts the
horizontal offset of the blob from the image center into a servo
correction. Use robot.plot() to watch the error shrink.

Hardware
--------
- Pan servo → S0 (single-pin port)
- Pi camera or USB webcam (connected to Raspberry Pi)

Tuning
------
Change TARGET_COLOR to one of: "red", "green", "blue", "yellow"
(or tune your own HSV bounds inside camera.color_mask).
"""

from redwing import Robot

TARGET_COLOR  = "red"
FRAME_WIDTH   = 640
SERVO_CENTER  = 150    # degrees (mid-point of 300° range)
KP            = 0.05   # proportional gain: pixels → degrees of correction

robot = Robot()

pan   = robot.S0.servo()     # 0–300° pan servo
cam   = robot.camera

robot.start()

pan.set_angle(SERVO_CENTER)  # start centered
current_angle = float(SERVO_CENTER)

while True:
    frame = cam.read()
    mask  = cam.color_mask(frame, TARGET_COLOR)
    blob  = cam.find_largest_contour(mask)

    if blob is not None:
        cx, cy, area = blob
        error = cx - FRAME_WIDTH / 2          # pixels left/right of center
        correction = KP * error
        current_angle = max(0, min(300, current_angle + correction))
        pan.set_angle(current_angle)

        robot.plot("blob_x",      cx)
        robot.plot("error_px",    error)
        robot.plot("servo_angle", current_angle)

    cam.show(frame)
    robot.sleep(0.05)
