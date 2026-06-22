"""Example 7 — Drive a fixed distance using an encoder.

Instead of driving for a fixed time (which varies with battery level),
this program drives until the encoder reaches a target tick count and
then stops.

You need to know your wheel's ticks-per-revolution and circumference
to convert encoder ticks to centimetres. Start with the values below
and tune them to match your robot.

Hardware
--------
- Motor controller → D0
- Quadrature encoder → D2  (both signals connected to D2's two pins)
"""

from redwing import Robot

TICKS_PER_REV  = 48       # encoder pulses per motor shaft revolution
GEAR_RATIO     = 30       # motor shaft revolutions per wheel revolution
WHEEL_DIAM_CM  = 6.5      # wheel diameter in centimetres

# Derived: encoder ticks per cm of wheel travel
TICKS_PER_CM = (TICKS_PER_REV * GEAR_RATIO) / (3.14159 * WHEEL_DIAM_CM)

TARGET_CM = 50            # drive 50 cm forward

robot = Robot()

motor   = robot.D0.motor()
encoder = robot.D2.encoder()
motor.attach_encoder(encoder)   # tells the firmware to pair them

robot.start()

encoder.reset()
target_ticks = int(TARGET_CM * TICKS_PER_CM)

robot.log(f"Driving {TARGET_CM} cm ({target_ticks} ticks)…")

motor.set_power(50)

while encoder.count < target_ticks:
    robot.log(f"  ticks: {encoder.count} / {target_ticks}")
    robot.sleep(0.05)

motor.stop()
robot.log("Done.")
