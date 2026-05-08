"""Example 5 — Encoder odometry.

Drives forward for a set number of encoder ticks (instead of a fixed
time), so the distance is consistent regardless of battery level.

You need to measure TICKS_PER_CM for your specific robot — see the
comment below for how to do that.

Hardware needed:
  Port 1: left motor
  Port 2: left encoder
  Port 3: right motor
  Port 4: right encoder
"""

import redwing

robot = redwing.Robot()

left_motor  = robot.D0.motor()
left_enc    = robot.D1.encoder()
right_motor = robot.D2.motor()
right_enc   = robot.D3.encoder()

right_motor.inverted = True

# Calibration:
# 1. Run the robot at speed=50 for exactly 1 meter.
# 2. Read left_enc.count and right_enc.count.
# 3. Average them and enter that number here.
TICKS_PER_CM = 45   # adjust for your robot

DRIVE_CM = 50   # how far to drive (centimeters)
DRIVE_TICKS = int(DRIVE_CM * TICKS_PER_CM)


def drive_ticks(ticks: int, speed: int = 50):
    """Drive forward a fixed number of encoder ticks."""
    left_enc.reset()
    right_enc.reset()

    left_motor.speed  = speed
    right_motor.speed = speed

    while left_enc.count < ticks and right_enc.count < ticks:
        robot.log(f"Left: {left_enc.count} ticks  Right: {right_enc.count} ticks")
        robot.sleep(0.05)

    robot.stop()


robot.log(f"Driving {DRIVE_CM} cm ({DRIVE_TICKS} ticks)...")
drive_ticks(DRIVE_TICKS)
robot.log("Done!")
