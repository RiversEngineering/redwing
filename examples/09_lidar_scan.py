"""Example 9 — Reading the 360° LIDAR sensor.

Prints the distance to the nearest object in front of the robot every
100 ms and sends the full scan to the dashboard radar view.

The LIDAR connects to the Raspberry Pi via USB. Make sure the device
is listed in docker-compose.yml, e.g.:
    REDWING_LIDAR: /dev/ttyUSB0

The sensor does not use a Pico port — no port configuration needed.

Hardware
--------
- 360° USB LIDAR (e.g. RPLIDAR A1/A2 or YDLidar)
  connected to the Raspberry Pi USB port
"""

from redwing import Robot

robot = Robot()

# offset_deg=0 means the sensor's forward direction matches the robot's.
# Use offset_deg=180 if the sensor is mounted facing backward.
lidar = robot.lidar(offset_deg=0)

robot.start()

while True:
    # nearest_in_range(center, half_width) looks in the arc
    # from (center - half_width) to (center + half_width) degrees.
    # 0° is always robot-forward after the offset is applied.
    front = lidar.nearest_in_range(center_deg=0, half_width_deg=30)

    robot.log(f"Nearest in front: {front:.0f} cm")
    robot.sleep(0.1)
