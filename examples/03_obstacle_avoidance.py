"""Example 3 — Obstacle avoidance.

The robot drives forward until it detects something closer than 25 cm,
then backs up, turns, and tries again.

Hardware needed:
  Port 1: left motor
  Port 2: right motor
  Port 3: HC-SR04 ultrasonic sensor (front-facing)
"""

import redwing

robot = redwing.Robot()

left   = robot.D0.motor()
right  = robot.D1.motor()
sensor = robot.D2.ultrasonic()

right.inverted = True   # adjust if your right motor drives the wrong direction

STOP_DISTANCE = 25   # cm — stop when something is closer than this

robot.log("Starting obstacle avoidance. Press Ctrl+C to stop.")

while True:
    distance = sensor.distance

    if sensor.in_range and distance < STOP_DISTANCE:
        robot.log(f"Obstacle at {distance:.1f} cm! Backing up and turning...")

        # Back up
        left.speed  = -50
        right.speed = -50
        robot.sleep(0.8)

        # Turn right
        left.speed  = 50
        right.speed = -50
        robot.sleep(0.6)

    else:
        # Clear path — drive forward
        left.speed  = 60
        right.speed = 60

    robot.sleep(0.05)   # check 20 times per second
