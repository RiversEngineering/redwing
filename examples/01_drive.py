"""Example 1 — Drive a single motor.

The simplest possible program. One motor runs at half power for two
seconds, then stops.

Hardware
--------
- Motor controller wired to port D0 (dual-pin, sign-magnitude mode)
"""

from redwing import Robot

robot = Robot()

motor = robot.D0.motor()   # configure D0 as a sign-magnitude motor

robot.start()              # lock in configuration and enable commands

motor.set_power(50)        # 50 % forward (-100 to +100)
robot.sleep(2)
motor.stop()
