"""Example 8 — Closed-loop velocity control with PID.

The RP2040 runs an onboard PID loop at 100 Hz that keeps the motor at a
target speed in encoder ticks per second, regardless of load or battery
level.

After tuning the PID gains you can call robot.plot() to watch the actual
velocity track the setpoint on the dashboard graph.

Hardware
--------
- Motor controller → D0
- Quadrature encoder → D2
"""

from redwing import Robot

# PID gains — tune these for your motor/encoder combination.
# Start with a small Kp (0.1–0.5) and zero Ki/Kd, then add Ki once
# the response looks stable.
KP = 0.3
KI = 0.05
KD = 0.01

TARGET_TICKS_PER_S = 200   # setpoint: 200 ticks per second

robot = Robot()

motor   = robot.D0.motor()
encoder = robot.D2.encoder()
motor.attach_encoder(encoder)
motor.set_pid(KP, KI, KD)

robot.start()

robot.log(f"Running at {TARGET_TICKS_PER_S} ticks/s — watch the dashboard graph.")

motor.set_velocity(TARGET_TICKS_PER_S)

while True:
    robot.plot("target",   TARGET_TICKS_PER_S)
    robot.plot("velocity", encoder.velocity)
    robot.sleep(0.05)
