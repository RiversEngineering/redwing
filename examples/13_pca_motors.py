"""Example 13 — Motor control via PCA9685 I²C PWM expander.

The PCA9685 adds 16 extra channels for servos or RC ESC motor
controllers, all via a single I²C connection to the Raspberry Pi.

Channels are accessed as robot.P0 through robot.P15.
PCA motors use the same RC servo signal as single-pin Pico ports:
  1500 µs = stop, 1100 µs = full reverse, 1900 µs = full forward.
set_power(-100 to +100) handles this mapping automatically.

Before running this program, connect a PCA9685 module to the Pi's
I²C bus (SDA/SCL) and power it from an appropriate supply.
Calibrate it from the Ports tab in the dashboard for best accuracy.

Hardware
--------
- PCA9685 I²C PWM expander connected to Raspberry Pi I²C bus
- Left  RC ESC / motor controller → PCA channel 0 (robot.P0)
- Right RC ESC / motor controller → PCA channel 1 (robot.P1)

Note: PCA motors do not use Pico ports — no D/S port configuration
needed. robot.start() is still required to finalize any Pico ports
that are used alongside the PCA channels.
"""

from redwing import Robot

robot = Robot()

left  = robot.P0.motor()    # PCA channel 0 → RC ESC
right = robot.P1.motor()    # PCA channel 1 → RC ESC

robot.start()               # still required even with no Pico ports

# Drive forward for 2 seconds
left.set_power(50)
right.set_power(50)
robot.sleep(2)

# Spin right
left.set_power(60)
right.set_power(-60)
robot.sleep(0.5)

# Stop
left.set_power(0)
right.set_power(0)
