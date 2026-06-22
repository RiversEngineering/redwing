"""Example 10 — LIDAR wall-following with PID.

The robot drives forward while a PID controller keeps it a fixed
distance from the wall on its right side. The LIDAR measures the
distance to the right wall on every loop iteration, and the error
(measured - desired) steers the robot left or right.

This is a classic single-axis PID application — tune Kp first, then
add Kd to reduce oscillation. Use robot.plot() to watch the error.

Hardware
--------
- Left motor controller  → D0
- Right motor controller → D1
- 360° USB LIDAR (connected to Raspberry Pi USB)

Diagram
-------
  +----wall----+
  |            |
  | →  robot   |  ← right wall at 90°
  |            |
"""

from redwing import Robot

TARGET_CM = 25   # desired distance from the right wall

KP = 1.5         # proportional gain
KD = 0.3         # derivative gain (dampens oscillation)
BASE_SPEED = 50  # straight-line speed

robot = Robot()

left  = robot.D0.motor()
right = robot.D1.motor()
lidar = robot.lidar()

robot.start()

prev_error = 0.0

while True:
    # Measure distance on the right side (90° clockwise from forward)
    right_dist = lidar.nearest_in_range(center_deg=90, half_width_deg=20)

    if right_dist <= 0 or right_dist > 200:
        # No wall detected — drive straight
        left.set_power(BASE_SPEED)
        right.set_power(BASE_SPEED)
        robot.sleep(0.05)
        continue

    error      = right_dist - TARGET_CM      # positive → too far, steer right
    derivative = error - prev_error
    prev_error = error

    correction = KP * error + KD * derivative

    # Positive correction steers right (reduce right, increase left)
    left.set_power(BASE_SPEED + correction)
    right.set_power(BASE_SPEED - correction)

    robot.plot("right_dist", right_dist)
    robot.plot("error",      error)

    robot.sleep(0.05)
