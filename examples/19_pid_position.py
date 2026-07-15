"""Example 19 — Closed-loop position control with PID.

The RP2040 runs an onboard PID loop at 100 Hz that drives a motor to a
target encoder tick count and holds it there — like a servo, but with a
DC motor and quadrature encoder.

Two methods are available:
  motor.go_to_position(target)         — move to an absolute tick count
  motor.move_by(delta)                 — move a relative number of ticks

Both accept an optional max_speed argument (0–100 %) to cap motor power
during the move — useful when approaching a hard stop or when precision
matters more than speed.

Tuning tips
-----------
Position PID error is in encoder ticks, not ticks/s, so the gains will be
very different from velocity PID.  Start here and adjust:

  KP — increase until the motor reaches position quickly without overshooting.
  KD — add to damp oscillation / overshoot near the target.
  KI — keep small or zero; a large KI can cause slow windup oscillation.

Hardware
--------
- Motor controller → D0
- Quadrature encoder → D2
"""

import time
from redwing import Robot

# PID gains — tune for your motor and encoder resolution.
KP = 0.8
KI = 0.0
KD = 0.05

robot = Robot()

motor   = robot.D0.motor()
encoder = robot.D2.encoder()
motor.attach_encoder(encoder)
motor.set_pid(KP, KI, KD)

robot.start()

# ── Helper: wait until the motor is within tolerance of its target ────────────

def wait_for_position(target: int, tolerance: int = 10, timeout: float = 5.0):
    """Block until encoder.count is within *tolerance* ticks of *target*."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if abs(encoder.count - target) <= tolerance:
            return True
        robot.plot("target",   target)
        robot.plot("position", encoder.count)
        robot.sleep(0.02)
    robot.log(f"Position timeout — stopped at tick {encoder.count}")
    return False


# ── Demo sequence ─────────────────────────────────────────────────────────────

robot.log("Resetting encoder to zero.")
encoder.reset()

# 1. Move to an absolute position at full speed.
robot.log("go_to_position(500) — full speed")
motor.go_to_position(500)
wait_for_position(500)
robot.sleep(1.0)

# 2. Move to a different absolute position at 40 % speed.
robot.log("go_to_position(0) — 40 % speed cap")
motor.go_to_position(0, max_speed=40)
wait_for_position(0)
robot.sleep(1.0)

# 3. Relative moves: three steps of 200 ticks forward.
for step in range(3):
    target = (step + 1) * 200
    robot.log(f"move_by(200) — step {step + 1}, target ≈ {target} ticks")
    motor.move_by(200)
    wait_for_position(target)
    robot.sleep(0.5)

# 4. Return to zero with a speed cap.
robot.log("move_by back to 0 — 50 % speed cap")
motor.go_to_position(0, max_speed=50)
wait_for_position(0)

robot.log("Done.")
motor.stop()
