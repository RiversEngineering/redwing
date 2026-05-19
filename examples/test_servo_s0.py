"""Servo test — S0 (300° servo, 500–2500 µs).

Sweeps the servo on port S0 from 0° to 300° and back, then holds at center.
Run this on the Pi with the daemon already running:

    python test_servo_s0.py
"""

import redwing

robot = redwing.Robot()

arm = robot.S0.servo()  # default: 300°, 500–2500 µs

robot.start()

robot.log("Servo test started on S0")

# Sweep 0 → 300
robot.log("Sweeping 0 → 300°")
for angle in range(0, 301, 5):
    arm.set_angle(angle)
    robot.sleep(0.02)

# Sweep 300 → 0
robot.log("Sweeping 300 → 0°")
for angle in range(300, -1, -5):
    arm.set_angle(angle)
    robot.sleep(0.02)

# Park at centre
arm.center()
robot.log("Done — parked at center (150°)")
