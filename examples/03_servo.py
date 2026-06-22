"""Example 3 — Servo sweep.

Sweeps a servo from one end of its travel to the other and back,
repeating forever.

Hardware
--------
- Servo connected to port S0 (single-pin)

The default Redwing servo has a 300° range (500–2500 µs).
For a standard 180° hobby servo use:
    arm = robot.S0.servo(max_deg=180, min_us=1000, max_us=2000)
"""

from redwing import Robot

robot = Robot()

arm = robot.S0.servo()    # default: 0–300° range

robot.start()

while True:
    arm.set_angle(0)
    robot.sleep(1)

    arm.set_angle(150)    # mid-point
    robot.sleep(0.5)

    arm.set_angle(300)
    robot.sleep(1)

    arm.set_angle(150)
    robot.sleep(0.5)
