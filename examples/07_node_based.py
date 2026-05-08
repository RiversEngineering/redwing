"""Example 7 — Node-based programming (advanced).

Uses the redwing.nodes system to run two independent loops concurrently:
  - ObstacleDetector: reads the sensor every 50ms
  - DriveController:  acts on sensor data to steer the robot

This pattern is useful when different parts of your code need to run
at different speeds, or when you want to keep sensing and acting separate.

Hardware needed:
  Port 1: left motor
  Port 2: right motor
  Port 3: HC-SR04 ultrasonic sensor
"""

import redwing
from redwing.nodes import Node, run_nodes

robot = redwing.Robot()

left   = robot.D0.motor()
right  = robot.D1.motor()
sensor = robot.D2.ultrasonic()

right.inverted = True


class ObstacleDetector(Node):
    """Reads the sensor and publishes distance on the "distance" channel."""

    async def run(self):
        while True:
            distance = sensor.distance
            await self.publish("distance", distance)
            await self.sleep(0.05)   # 20Hz


class DriveController(Node):
    """Receives distance readings and controls the motors."""

    async def run(self):
        while True:
            distance = await self.receive("distance")

            if not sensor.in_range or distance > 30:
                left.speed  = 60
                right.speed = 60
            elif distance > 15:
                # Slow down when close
                left.speed  = 30
                right.speed = 30
            else:
                # Too close — back up and turn
                left.speed  = -40
                right.speed = 10

            robot.log(f"Distance: {distance:.1f} cm")


robot.log("Starting node-based obstacle avoidance. Press Ctrl+C to stop.")

# Start both nodes — they run concurrently until Ctrl+C
run_nodes(ObstacleDetector(), DriveController())
