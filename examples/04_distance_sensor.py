"""Example 4 — Read an ultrasonic distance sensor.

Prints the distance to the nearest object every half second.
`distance` returns centimetres, or -1 if no echo was received
(object too far or out of the sensor's beam).

Hardware
--------
- HC-SR04 ultrasonic sensor → D2 (dual-pin port required)
"""

from redwing import Robot

robot = Robot()

sensor = robot.D2.ultrasonic()

robot.start()

while True:
    d = sensor.distance

    if d < 0:
        robot.log("No echo — object out of range")
    else:
        robot.log(f"Distance: {d:.1f} cm")

    robot.sleep(0.5)
