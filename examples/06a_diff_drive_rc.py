"""Example — Gamepad-controlled differential drive (tank steering).

Left stick Y-axis controls forward/backward movement
Right stick X-axis controls turning. 
Press A to stop all motors.

Connect a gamepad via USB or the virtual controller in the dashboard.

Make sure both motors drive forwards when power is positive.

Hardware
--------
- Left motor controller  → D0
- Right motor controller → D1
- Gamepad (USB or virtual dashboard controller)
"""

# import redwing library
from redwing import Robot

# set up robot object
robot = Robot()

# set up motor connections (must match hardware connections)
left  = robot.D0.motor()
right = robot.D1.motor()
gamepad = robot.gamepad

robot.start()

# run forever
while True:
    # joysticks return -1.0 to 1.0
    # motors expect -100 to 100
    # run at half speed to start
    throttle = gamepad.left_y * 50
    turn = gamepad.right_x * 50

    left_pwr = throttle + turn
    right_pwr = throttle - turn

    if gamepad.just_pressed_a:
        robot.stop()
        robot.log("Emergency stop")
    else:
        left.set_power(left_pwr)
        right.set_power(right_pwr)

    # 50 Hz control loop; ESSENTIAL
    robot.sleep(0.02)   
