"""Example 2 — Two-motor differential drive.

Uses a left and right motor to drive forward, spin in place, reverse,
and stop in sequence.

Hardware
--------
- Left motor controller  → D0 (dual-pin, sign-magnitude)
- Right motor controller → D1 (dual-pin, sign-magnitude)

If one motor runs backward, set its `inverted` flag:
    right.inverted = True
"""

from redwing import Robot

robot = Robot()

left  = robot.D0.motor()
right = robot.D1.motor()

# right.inverted = True   # uncomment if right wheel runs the wrong way

robot.start()

# Drive forward
left.set_power(60)
right.set_power(60)
robot.sleep(2)

# Spin right in place
left.set_power(60)
right.set_power(-60)
robot.sleep(0.5)

# Reverse
left.set_power(-40)
right.set_power(-40)
robot.sleep(1)

robot.stop()
