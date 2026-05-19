"""Example 8 — Closed-loop velocity control.

Uses the RP2040's onboard PID (100 Hz) to hold a target motor speed
in encoder ticks per second, independent of load or battery voltage.

Hardware needed:
  D0 — motor
  D1 — quadrature encoder on that motor

Run this on the Pi with the daemon already running:

    python 08_velocity_control.py
"""

import redwing

robot = redwing.Robot()

motor = robot.D0.motor()
enc   = robot.D1.encoder()

motor.attach_encoder(enc)

# Default PID gains (kp=1.0, ki=0.5, kd=0.1) are a starting point.
# If the motor overshoots/oscillates: lower kp, lower ki.
# If it's slow to reach target: raise kp.
# motor.set_pid(kp=1.0, ki=0.5, kd=0.1)

robot.start()

robot.log("=== Velocity control test ===")
robot.log("Measuring free-spin speed — watch the actual velocity values.")
robot.log("Use these to pick a realistic target.\n")

# ── Step 1: find free-spin speed ──────────────────────────────────────
# Run open-loop at 50% to see what velocity the motor naturally reaches.
motor.set_speed(50)
for _ in range(30):
    robot.log(f"open-loop 50%  actual: {enc.velocity:+.0f} ticks/s")
    robot.sleep(0.1)
motor.stop()
robot.sleep(0.5)

# ── Step 2: closed-loop velocity hold ────────────────────────────────
# Set a target roughly 80% of what you saw above.
# Adjust TARGET_TICKS_S to match your motor + encoder.
TARGET_TICKS_S = 200   # ← tune this after seeing Step 1 output

robot.log(f"\nHolding {TARGET_TICKS_S} ticks/s for 5 seconds...")
motor.set_velocity(TARGET_TICKS_S)

for _ in range(50):
    robot.log(
        f"target: {TARGET_TICKS_S:+5.0f}  "
        f"actual: {enc.velocity:+5.0f}  "
        f"error: {TARGET_TICKS_S - enc.velocity:+5.0f}"
    )
    robot.sleep(0.1)

# ── Step 3: reverse ───────────────────────────────────────────────────
robot.log(f"\nReversing to -{TARGET_TICKS_S} ticks/s for 3 seconds...")
motor.set_velocity(-TARGET_TICKS_S)

for _ in range(30):
    robot.log(
        f"target: {-TARGET_TICKS_S:+5.0f}  "
        f"actual: {enc.velocity:+5.0f}  "
        f"error: {-TARGET_TICKS_S - enc.velocity:+5.0f}"
    )
    robot.sleep(0.1)

motor.stop()
robot.log("\nDone.")
