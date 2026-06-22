"""Example 11 — LIDAR mapping with dead-reckoning odometry.

Drives forward while building a map of the environment. The robot's
position is estimated from encoder ticks (dead-reckoning), and every
LIDAR point is converted from robot-relative polar coordinates to
world-frame Cartesian coordinates and sent to the dashboard map view.

This is an introduction to the core idea behind SLAM: combining
motion estimates with sensor readings to build a map.

Hardware
--------
- Left motor controller  → D0
- Left encoder           → D2
- Right motor controller → D1
- Right encoder          → D3
- 360° USB LIDAR (connected to Raspberry Pi USB)

Tuning
------
Set TICKS_PER_CM to match your robot's encoder and wheel geometry.
You can measure this by driving 1 m and reading encoder.count.
"""

import math
from redwing import Robot

TICKS_PER_CM   = 43.0    # encoder ticks per centimetre of wheel travel
TRACK_WIDTH_CM = 20.0    # distance between left and right wheels

robot = Robot()

left        = robot.D0.motor()
left_enc    = robot.D2.encoder()
right       = robot.D1.motor()
right_enc   = robot.D3.encoder()
left.attach_encoder(left_enc)
right.attach_encoder(right_enc)

lidar = robot.lidar()

robot.start()

# World-frame pose: (x_cm, y_cm, heading_radians)
x, y, heading = 0.0, 0.0, 0.0
prev_left  = 0
prev_right = 0

robot.map_pose(x, y, math.degrees(heading))

robot.log("Mapping — drive the robot around the space.")

left.set_power(40)
right.set_power(40)

while True:
    # --- Odometry ---
    cur_left  = left_enc.count
    cur_right = right_enc.count

    dl = (cur_left  - prev_left)  / TICKS_PER_CM
    dr = (cur_right - prev_right) / TICKS_PER_CM
    prev_left  = cur_left
    prev_right = cur_right

    d_center  = (dl + dr) / 2
    d_heading = (dr - dl) / TRACK_WIDTH_CM    # radians

    heading += d_heading
    x       += d_center * math.cos(heading)
    y       += d_center * math.sin(heading)

    robot.map_pose(x, y, math.degrees(heading))

    # --- Map LIDAR scan into world frame ---
    points = []
    for angle_deg, dist_cm in lidar.scan():
        if dist_cm <= 0 or dist_cm > 400:
            continue
        # Robot-relative polar → Cartesian
        angle_rad  = math.radians(angle_deg) + heading
        px = x + dist_cm * math.cos(angle_rad)
        py = y + dist_cm * math.sin(angle_rad)
        points.append((px, py))

    if points:
        robot.map_points(points)

    robot.sleep(0.05)
