"""Example 6 — Gamepad-controlled differential drive (tank steering).

Left stick Y-axis drives the left wheel; right stick Y-axis drives the
right wheel. Press A to stop all motors.

Connect a gamepad via USB or the virtual controller in the dashboard.

Hardware
--------
- Left motor controller  → D0
- Right motor controller → D1
- Gamepad (USB or virtual dashboard controller)

Controls
--------
- Left  stick Y  → left wheel speed
- Right stick Y  → right wheel speed
- A button       → emergency stop
"""

from redwing import Robot

robot = Robot()

left  = robot.D0.motor()
right = robot.D1.motor()
gp    = robot.gamepad

robot.start()

robot.log("Waiting for gamepad…")

while True:
    if not gp.connected:
        robot.sleep(0.1)
        continue

    if gp.just_pressed_a:
        robot.stop()
        robot.log("Emergency stop")

    # Stick axes return -1.0 to +1.0; scale to -100..+100 for set_power
    left.set_power(gp.left_y * 100)
    right.set_power(gp.right_y * 100)

    robot.sleep(0.02)   # 50 Hz control loop
