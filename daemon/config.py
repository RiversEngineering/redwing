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

# Cap OpenCV's internal thread pool. The feed's per-frame work (resize + JPEG
# encode at 640×480) is tiny and gains nothing from more threads, so limiting
# it costs no feed performance — it just keeps cores free so a student's heavy
# vision work in the code-server container can't starve the capture loop on a
# 4-core Pi 4.
OPENCV_THREADS = int(os.getenv("REDWING_CV_THREADS", "2"))

# LIDAR — leave empty to disable; set to e.g. /dev/ttyUSB0 to enable
LIDAR_PORT = os.getenv("REDWING_LIDAR", "")

# RP2040 firmware image flashed by the dashboard's "Flash Firmware" button.
# Built separately via firmware/build.sh — this just points at the resulting .uf2.
FIRMWARE_UF2_PATH = os.getenv("REDWING_FIRMWARE_UF2", "/app/firmware/redwing.uf2")

# Battery monitor — I²C bus number for the MAX17043/17048 fuel gauge.
# Set to -1 to disable.
BATTERY_I2C_BUS = int(os.getenv("REDWING_BATTERY_BUS", "1"))

def _pi_model() -> str:
    """Read the Raspberry Pi model string from /proc/device-tree/model or /proc/cpuinfo."""
    try:
        with open("/proc/device-tree/model") as f:
            return f.read().rstrip("\x00")
    except OSError:
        pass
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("Model"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""

PI_MODEL = _pi_model()

# Number of Li-Ion/LiPo cells in series.  Set to 0 for auto-detection
# (daemon infers cell count from the first voltage reading: <5V→1S, <9V→2S,
# <13V→3S, <17V→4S).  Defaults to 4 on Pi 5 (which uses 4S battery modules
# with internal voltage dividers that report per-cell voltage).
# Override with REDWING_BATTERY_CELLS to force a specific count on any robot.
_default_cells = 4 if "Raspberry Pi 5" in PI_MODEL else 0
BATTERY_CELLS = int(os.getenv("REDWING_BATTERY_CELLS", str(_default_cells)))

