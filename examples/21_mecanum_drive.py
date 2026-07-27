"""Example 21 — Mecanum drive with dead-reckoning odometry.

Demonstrates the MecanumDrive API: forward, backward, strafing, diagonal
movement, rotation, and reading the robot's estimated pose.

Mecanum wheels let the robot slide sideways without turning, making it
possible to move in any direction independently of which way the robot
is facing.

Hardware
--------
Both motors and encoders require dual-pin D ports (two signal wires each).
S ports are single-pin only and cannot drive sign-magnitude motors or decode
quadrature encoders.

A 4-motor mecanum with 4 encoders uses all 8 D ports:

  Front-left  motor → D0      Front-right motor → D1
  Back-left   motor → D2      Back-right  motor → D3
  Front-left  enc   → D4      Front-right enc   → D5
  Back-left   enc   → D6      Back-right  enc   → D7
  IMU (BNO085)      → I²C port (GP4/GP5) — optional but strongly recommended

Note: D6 = UART1 and D7 = UART0.  If you are also using a UART device
(Bluetooth, GPS, etc.) swap those encoders to a different peripheral bus
or drop to a 2-encoder configuration.

  Label your motors by physical position on the robot (front/back,
  left/right) — not by wiring order.  Use motor.inverted = True on any
  motor that spins the wrong direction when given a positive power command.

Tune the constants below to match your robot before running.
"""

import redwing

# ── Robot geometry ─────────────────────────────────────────────────────────────
WHEEL_DIAM_MM  = 100     # mecanum wheel diameter in millimetres
TRACK_WIDTH_MM = 300     # left-to-right distance between wheel centres (mm)
WHEELBASE_MM   = 280     # front-to-back distance between wheel centres (mm)
TICKS_PER_REV  = 1440   # encoder pulses per full wheel revolution

# ── Setup ──────────────────────────────────────────────────────────────────────
robot = redwing.Robot()

# Configure each corner: motor + its encoder.
# Flip .inverted on any motor that runs backwards.
fl_m = robot.motor(robot.D0);  fl_e = robot.encoder(robot.D4)
fr_m = robot.motor(robot.D1);  fr_e = robot.encoder(robot.D5)
bl_m = robot.motor(robot.D2);  bl_e = robot.encoder(robot.D6)
br_m = robot.motor(robot.D3);  br_e = robot.encoder(robot.D7)

# fr_m.inverted = True   # uncomment if front-right runs backwards
# br_m.inverted = True   # uncomment if back-right runs backwards

# Wrap each corner into a (Motor, Encoder) pair for the drive.
# If a corner uses TWO motors (e.g. a larger robot), use motor_group:
#   fl_group = robot.motor_group(fl_m1, fl_m2, encoder=fl_e)
# then pass fl_group directly instead of (fl_m, fl_e).
drive = robot.mecanum_drive(
    fl=(fl_m, fl_e),
    fr=(fr_m, fr_e),
    bl=(bl_m, bl_e),
    br=(br_m, br_e),
    imu=robot.imu(),           # remove this line if no IMU is attached
    wheel_diameter_mm=WHEEL_DIAM_MM,
    track_width_mm=TRACK_WIDTH_MM,
    wheelbase_mm=WHEELBASE_MM,
    ticks_per_rev=TICKS_PER_REV,
)

robot.start()

# ── Demo sequence ──────────────────────────────────────────────────────────────

robot.log("Starting mecanum drive demo")
robot.clear_map()

# Basic cardinal directions
robot.log("Forward 0.5 m")
drive.forward(0.5, power=50)
robot.sleep(0.3)

robot.log("Backward 0.5 m")
drive.backward(0.5, power=50)
robot.sleep(0.3)

robot.log("Strafe right 0.4 m")
drive.strafe_right(0.4, power=50)
robot.sleep(0.3)

robot.log("Strafe left 0.4 m")
drive.strafe_left(0.4, power=50)
robot.sleep(0.3)

# Diagonal movement using strafe(distance, angle)
# Angle: 0° = forward, 90° = right, 180° = backward, 270° = left
robot.log("Diagonal: forward-right 0.5 m at 45°")
drive.strafe(0.5, angle_deg=45, power=50)
robot.sleep(0.3)

robot.log("Diagonal: back to start at 225° (back-left)")
drive.strafe(0.5, angle_deg=225, power=50)
robot.sleep(0.3)

# Rotations — robot stays in place
robot.log("Turn right 90°")
drive.turn_right(90, power=40)
robot.sleep(0.3)

robot.log("Turn left 90°  (back to original heading)")
drive.turn_left(90, power=40)
robot.sleep(0.3)

# Pose after the above moves should be close to (0, 0, 0°)
x, y, hdg = drive.pose
robot.log(f"Pose after rotations → x={x:.2f} m  y={y:.2f} m  heading={hdg:.1f}°")

# Continuous holonomic motion: move(vx, vy, omega)
#   vx    = forward/backward  (-100 to +100)
#   vy    = right strafe       (-100 to +100, positive = right)
#   omega = rotation           (-100 to +100, positive = CCW)
robot.log("Continuous: circle (forward + CCW rotation) for 2 s")
drive.move(vx=40, vy=0, omega=20)
robot.sleep(2.0)
drive.stop()
robot.sleep(0.3)

robot.log("Continuous: crab sideways right for 1 s")
drive.move(vx=0, vy=50, omega=0)
robot.sleep(1.0)
drive.stop()
robot.sleep(0.3)

# Final pose
x, y, hdg = drive.pose
robot.log(f"Final pose → x={x:.2f} m  y={y:.2f} m  heading={hdg:.1f}°")
robot.log("Demo complete.")
