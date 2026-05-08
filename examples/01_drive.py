"""Example 1 — Drive forward, then stop.

This is the simplest possible program. It drives the robot forward
for 2 seconds, then stops.

Hardware needed:
  Port 1: left motor  (sign-magnitude motor controller)
  Port 2: right motor (sign-magnitude motor controller)
"""

import redwing

robot = redwing.Robot()

left  = robot.D0.motor()
right = robot.D1.motor()

# If the right motor drives backward when you expect forward,
# set right.inverted = True instead of rewiring the motor.

robot.log("Driving forward for 2 seconds...")

left.speed  = 60   # 60% forward
right.speed = 60

robot.sleep(2)

robot.stop()
robot.log("Done!")
