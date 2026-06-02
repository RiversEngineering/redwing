"""Daemon configuration — overridable via environment variables."""

import os

# Serial port where the RP2040 appears
SERIAL_PORT  = os.getenv("REDWING_SERIAL",    "/dev/ttyACM0")
SERIAL_BAUD  = int(os.getenv("REDWING_BAUD",  "115200"))

# RP2040 state stream rate in Hz (also sent as SET_RATE on startup)
STREAM_HZ    = int(os.getenv("REDWING_HZ",    "50"))

# ZeroMQ ports
ZMQ_PUB_PORT = int(os.getenv("REDWING_PUB",   "5555"))  # state → library SUBs
ZMQ_PULL_PORT = int(os.getenv("REDWING_PULL",  "5556"))  # commands ← library PUSHes
ZMQ_REP_PORT  = int(os.getenv("REDWING_REP",   "5557"))  # config REQ/REP

# Web server
WEB_HOST     = os.getenv("REDWING_HOST", "0.0.0.0")
WEB_PORT     = int(os.getenv("REDWING_PORT",   "8080"))

# Camera
CAMERA_INDEX  = int(os.getenv("REDWING_CAM",     "0"))
CAMERA_WIDTH  = int(os.getenv("REDWING_CAM_W",  "640"))
CAMERA_HEIGHT = int(os.getenv("REDWING_CAM_H",  "480"))
CAMERA_FPS    = int(os.getenv("REDWING_CAM_FPS", "30"))
MJPEG_QUALITY = int(os.getenv("REDWING_JPEG",    "75"))

# LIDAR — leave empty to disable; set to e.g. /dev/ttyUSB0 to enable
LIDAR_PORT = os.getenv("REDWING_LIDAR", "")

# Battery monitor — I²C bus number for the MAX17043/17048 fuel gauge.
# Set to -1 to disable.
BATTERY_I2C_BUS = int(os.getenv("REDWING_BATTERY_BUS", "1"))
