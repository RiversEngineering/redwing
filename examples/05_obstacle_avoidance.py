"""Example 5 — Obstacle avoidance.

Drives forward until something is closer than 25 cm, then backs up,
turns, and tries again.

The robot is always in one of three states: "drive", "back_up", or
"turn". Each loop reads the sensor, decides which state to be in and
what power that state needs, then sets the motors once at the end.

Hardware
--------
- Left motor controller  → D0
- Right motor controller → D1
- HC-SR04 ultrasonic     → D2
"""

import time

from redwing import Robot

STOP_DISTANCE_CM = 25
BACK_UP_SECONDS  = 0.5
TURN_SECONDS     = 0.4

robot = Robot()

left   = robot.D0.motor()
right  = robot.D1.motor()
sensor = robot.D2.ultrasonic()

robot.start()

state       = "drive"
state_start = time.monotonic()   # when the current state began

while True:
    # INPUT
    distance = sensor.distance
    valid    = sensor.valid
    now      = time.monotonic()
    time_in_state = now - state_start

    # DECIDE: which state should we be in?
    if state == "drive" and valid and distance < STOP_DISTANCE_CM:
        state = "back_up"
        state_start = now
    elif state == "back_up" and time_in_state > BACK_UP_SECONDS:
        state = "turn"
        state_start = now
    elif state == "turn" and time_in_state > TURN_SECONDS:
        state = "drive"
        state_start = now

    # DECIDE: throttle and turn for that state
    throttle = 60                    # default: drive forward
    turn     = 0
    if state == "back_up":
        throttle = -50
    elif state == "turn":
        throttle = 0
        turn     = 60                # spin right in place

    left_power  = throttle + turn
    right_power = throttle - turn

    # OUTPUT
    left.set_power(left_power)
    right.set_power(right_power)

    robot.sleep(0.05)
