"""Redwing — robotics platform library for high school students.

Basic usage::

    import redwing

    robot = redwing.Robot()

    left  = robot.port1.motor()
    right = robot.port2.motor()

    left.speed  = 60
    right.speed = 60
    robot.sleep(2)
    robot.stop()

For node-based (advanced) programming::

    from redwing.nodes import Node, run_nodes
"""

from .robot import Robot
from .odometry import DifferentialDrive, MecanumDrive
from .devices.motor import MotorGroup

__all__ = ["Robot", "DifferentialDrive", "MecanumDrive", "MotorGroup"]
__version__ = "0.1.0"
