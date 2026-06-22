"""Example 14 — Node-based concurrent programming.

The nodes system lets different parts of your code run at their own
pace without blocking each other. Nodes communicate through named
channels: one node publishes values, another receives them.

This example runs two nodes simultaneously:
  - SensorNode: reads the ultrasonic sensor at 20 Hz and publishes
                the distance on the "distance" channel
  - DriveNode:  receives each new distance reading and adjusts the
                motor powers accordingly

Hardware
--------
- Left motor controller  → D0
- Right motor controller → D1
- HC-SR04 ultrasonic     → D2
"""

from redwing import Robot
from redwing.nodes import Node, run_nodes

robot = Robot()

left   = robot.D0.motor()
right  = robot.D1.motor()
sensor = robot.D2.ultrasonic()

robot.start()          # must be called before run_nodes()


class SensorNode(Node):
    """Reads the sensor at 20 Hz and broadcasts the distance."""

    async def run(self):
        while True:
            await self.publish("distance", sensor.distance)
            await self.sleep(0.05)


class DriveNode(Node):
    """Reacts to distance readings to steer the robot."""

    async def run(self):
        while True:
            distance = await self.receive("distance")

            if distance < 0 or distance > 30:
                # Clear path or no echo — drive forward
                left.set_power(60)
                right.set_power(60)
            elif distance > 15:
                # Getting close — slow down
                left.set_power(30)
                right.set_power(30)
            else:
                # Too close — back up and turn
                left.set_power(-40)
                right.set_power(10)

            robot.log(f"Distance: {distance:.1f} cm")


# run_nodes() is blocking — it starts all nodes and runs until Ctrl+C
run_nodes(SensorNode(), DriveNode())
