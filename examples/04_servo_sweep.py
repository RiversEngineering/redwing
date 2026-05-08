"""Example 4 — Servo sweep.

Sweeps a servo back and forth continuously.

Hardware needed:
  Port 5: RC servo
"""

import redwing

robot = redwing.Robot()

arm = robot.S0.servo()

robot.log("Sweeping servo. Press Ctrl+C to stop.")

while True:
    # Sweep from 0° to 180°
    for angle in range(0, 181, 5):
        arm.angle = angle
        robot.sleep(0.02)

    # Sweep back from 180° to 0°
    for angle in range(180, -1, -5):
        arm.angle = angle
        robot.sleep(0.02)
