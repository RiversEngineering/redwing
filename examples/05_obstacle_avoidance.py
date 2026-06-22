"""Example 5 — Obstacle avoidance.

Drives forward until something is closer than 25 cm, then backs up,
turns, and tries again.

Hardware
--------
- Left motor controller  → D0
- Right motor controller → D1
- HC-SR04 ultrasonic     → D2
"""

from redwing import Robot

robot = Robot()

left   = robot.D0.motor()
right  = robot.D1.motor()
sensor = robot.D2.ultrasonic()

robot.start()

while True:
    d = sensor.distance

    if d > 0 and d < 25:
        # Obstacle — back up then turn right
        left.set_power(-50)
        right.set_power(-50)
        robot.sleep(0.5)

        left.set_power(60)
        right.set_power(-60)
        robot.sleep(0.4)
    else:
        # Path clear — drive forward
        left.set_power(60)
        right.set_power(60)

    robot.sleep(0.05)
