"""Example 20 — Differential drive with dead-reckoning odometry.

Demonstrates the DifferentialDrive API: forward, backward, turns, and
reading the robot's estimated pose.  Two versions are shown:

  • 4-motor (two motors per side using MotorGroup) — default config.
  • Simple (2 motors, one per side) — see commented block below.

The drive tracks position automatically using encoder counts fused with
the IMU heading (BNO085/BNO055) or gyro integration (MPU-6050).  The
estimated pose is sent to the dashboard Map tab in real time.

Port layout
-----------
Motors and encoders both require dual-pin D ports (two signal wires each).
S ports are single-pin only and cannot be used for motors or encoders.

4-motor config (uses D0–D5):
  Front-left  motor → D0      Front-right motor → D1
  Rear-left   motor → D2      Rear-right  motor → D3
  Left encoder      → D4      Right encoder     → D5
  IMU (BNO085)      → I²C port (GP4/GP5) — optional but recommended

2-motor config (uses D0–D3):
  Left motor        → D0      Right motor       → D1
  Left encoder      → D2      Right encoder     → D3

Tune the constants below to match your robot before running.
"""

import redwing

# ── Robot geometry ─────────────────────────────────────────────────────────────
WHEEL_DIAM_MM  = 60      # drive wheel diameter in millimetres
TRACK_WIDTH_MM = 280     # distance between left and right wheel centres (mm)
TICKS_PER_REV  = 1440   # encoder pulses per full wheel revolution

# ── Setup ──────────────────────────────────────────────────────────────────────
robot = redwing.Robot()

# ── 4-MOTOR CONFIG (default) ───────────────────────────────────────────────────
# Two motors per side grouped together so they always move as one.
# Flip .inverted on any motor that runs the wrong direction.
fl = robot.motor(robot.D0)   # front-left
rl = robot.motor(robot.D2)   # rear-left
fr = robot.motor(robot.D1)   # front-right
rr = robot.motor(robot.D3)   # rear-right

# rl.inverted = True   # uncomment if rear-left runs backwards
# fr.inverted = True   # uncomment if front-right runs backwards

le = robot.encoder(robot.D4)
re = robot.encoder(robot.D5)

left  = robot.motor_group(fl, rl, encoder=le)
right = robot.motor_group(fr, rr, encoder=re)

drive = robot.differential_drive(
    left=left,
    right=right,
    imu=robot.imu(),           # remove this line if no IMU is attached
    wheel_diameter_mm=WHEEL_DIAM_MM,
    track_width_mm=TRACK_WIDTH_MM,
    ticks_per_rev=TICKS_PER_REV,
)

# ── SIMPLE CONFIG (2-motor) ────────────────────────────────────────────────────
# Uncomment this block and comment out the 4-motor block above.
#
# lm = robot.motor(robot.D0)
# rm = robot.motor(robot.D1)
# rm.inverted = True
# le = robot.encoder(robot.D2)
# re = robot.encoder(robot.D3)
#
# drive = robot.differential_drive(
#     left_motor=lm,   right_motor=rm,
#     left_encoder=le, right_encoder=re,
#     imu=robot.imu(),
#     wheel_diameter_mm=WHEEL_DIAM_MM,
#     track_width_mm=TRACK_WIDTH_MM,
#     ticks_per_rev=TICKS_PER_REV,
# )

robot.start()

# ── Demo sequence ──────────────────────────────────────────────────────────────

robot.log("Starting differential drive demo")
robot.clear_map()

# Drive a simple square
# Each leg: forward 0.5 m, then turn 90° right
for leg in range(4):
    robot.log(f"Leg {leg + 1}: forward 0.5 m")
    drive.forward(0.5, power=50)
    robot.sleep(0.3)            # brief pause between moves

    robot.log(f"Leg {leg + 1}: turn right 90°")
    drive.turn_right(90, power=40)
    robot.sleep(0.3)

    x, y, hdg = drive.pose
    robot.log(f"  Pose → x={x:.2f} m  y={y:.2f} m  heading={hdg:.1f}°")

# Drive backward a short distance
robot.log("Reversing 0.2 m")
drive.backward(0.2, power=40)
robot.sleep(0.3)

# Turn left using the signed rotate() method
robot.log("Rotating 45° counter-clockwise")
drive.rotate(45, power=35)
robot.sleep(0.3)

# Continuous drive example: gentle arc for 1 second
robot.log("Arcing right for 1 s")
drive.drive(forward=50, turn=-20)   # negative turn = right (clockwise)
robot.sleep(1.0)
drive.stop()
robot.sleep(0.3)

# Final pose report
x, y, hdg = drive.pose
robot.log(f"Final pose → x={x:.2f} m  y={y:.2f} m  heading={hdg:.1f}°")
robot.log("Demo complete.")
