"""Example 2 — Read a distance sensor.

Reads the ultrasonic sensor and prints the distance every half second.

Hardware needed:
  Port 3: HC-SR04 ultrasonic distance sensor
"""

import redwing

robot = redwing.Robot()

sensor = robot.D2.ultrasonic()

robot.log("Reading distance sensor. Press Ctrl+C to stop.")

while True:
    distance = sensor.distance   # centimeters

    if sensor.in_range:
        robot.log("Distance:", distance, "cm")
    else:
        robot.log("Nothing detected within range.")

    robot.sleep(0.5)
