"""Shared in-memory state for the daemon.

All subsystems read/write this single object. Access is protected by an
asyncio.Lock — always use ``async with state.lock`` before modifying.
"""

import asyncio
import time
from typing import Any


class GamepadState:
    """Mutable gamepad snapshot updated by the virtual controller (WebSocket)
    and the physical controller reader (evdev). Last write wins."""

    __slots__ = (
        "lx", "ly", "rx", "ry",
        "a", "b", "x", "y",
        "up", "down", "left", "right",
        "lb", "rb", "lt", "rt",
        "connected", "source",
    )

    def __init__(self):
        self.lx: float = 0.0
        self.ly: float = 0.0
        self.rx: float = 0.0
        self.ry: float = 0.0
        self.a: bool = False
        self.b: bool = False
        self.x: bool = False
        self.y: bool = False
        self.up: bool = False
        self.down: bool = False
        self.left: bool = False
        self.right: bool = False
        self.lb: bool  = False
        self.rb: bool  = False
        self.lt: float = 0.0
        self.rt: float = 0.0
        self.connected: bool = False
        self.source: str = "none"   # "virtual", "physical", or "none"

    def to_dict(self) -> dict:
        return {
            "lx": self.lx, "ly": self.ly,
            "rx": self.rx, "ry": self.ry,
            "a": self.a, "b": self.b,
            "x": self.x, "y": self.y,
            "up": self.up, "down": self.down,
            "left": self.left, "right": self.right,
            "lb": self.lb, "rb": self.rb,
            "lt": self.lt, "rt": self.rt,
            "connected": self.connected,
            "source": self.source,
        }

    def reset(self):
        self.lx = self.ly = self.rx = self.ry = 0.0
        self.a = self.b = self.x = self.y = False
        self.up = self.down = self.left = self.right = False
        self.lb = self.rb = False
        self.lt = self.rt = 0.0
        self.connected = False
        self.source = "none"


class SharedState:
    def __init__(self):
        self.lock = asyncio.Lock()
        self._start = time.monotonic()

        # RP2040 connection status (updated by rp2040.py on connect/disconnect)
        self.rp2040_connected: bool = False

        # Latest data from RP2040
        self.rp2040_ts: int = 0           # RP2040 millisecond timestamp
        self.ports: dict[str, Any] = {}   # port_id → port data dict

        # Port configuration metadata (set by IPC handler on CONFIGURE)
        self.port_config: dict[str, str] = {}   # port_id → type string
        self.config_finalized: bool = False      # True after CMD_CONFIG_DONE is ACKed

        # Encoder → motor attachment map (motor_port → encoder_port)
        self.encoder_map: dict[int, int] = {}

        # PID target velocities for closed-loop motors (port_id → ticks/s × 10)
        self.target_velocities: dict[int, float] = {}

        # UART RX bytes per port (14=D6/UART1, 15=D7/UART0), accumulated between broadcasts
        self.uart_rx_buffers: dict[int, bytearray] = {14: bytearray(), 15: bytearray()}

        # Latest LIDAR scan: list of (angle_deg, distance_cm) tuples, or None
        self.lidar_scan: list | None = None

        # LIDAR display configuration
        self.lidar_offset_deg: float  = 0.0    # mounting rotation offset (degrees CW)
        self.lidar_x_offset_cm: float = 0.0    # LIDAR X position from robot centre (+ve = right)
        self.lidar_y_offset_cm: float = 0.0    # LIDAR Y position from robot centre (+ve = forward)
        self.lidar_max_cm: float      = 400.0  # radar display radius (cm) — never code-locked
        self.lidar_code_configured: bool = False  # True once student code sets offset/xy

        # IMU mounting orientation (yaw/pitch/roll in degrees)
        self.imu_mount_yaw:      float = 0.0
        self.imu_mount_pitch:    float = 0.0
        self.imu_mount_roll:     float = 0.0
        self.imu_mount_code_set: bool  = False  # True once student code calls set_mount_rotation()

        # Per-port invert overrides (motor direction / encoder count direction)
        self.port_invert:          dict = {}    # str(port_id) → bool
        self.port_invert_code_set: set  = set() # port IDs where student code set inverted

        # Latest camera frame as JPEG bytes (seeded with placeholder by CameraCapture)
        self.camera_frame: bytes | None = None
        self.camera_frame_b64: str = ""   # base64-encoded version for student library
        # If student called camera_show(frame), this holds the override frame
        self.camera_override: bytes | None = None
        self.show_raw: bool = True   # True = show live feed; False = show override

        # Battery (MAX17043/17048 or INA219 via Pi I²C — auto-detected)
        self.battery_present: bool  = False
        self.battery_voltage: float = 0.0    # pack voltage in V (cell_v × cell_count)
        self.battery_soc:     float = 0.0    # state of charge in %
        self.battery_chip:    str   = ""     # detected chip name

        # Gamepad input (virtual iPad controller or physical USB controller)
        self.gamepad = GamepadState()

        # Log buffer for the dashboard (newest last)
        self.logs: list[dict] = []
        self._max_logs = 500
        self._log_total_count = 0  # monotonically increasing; never reset by trim

        # Student plot buffer — {label, value, ts} entries from robot.plot()
        self.plot_points: list[dict] = []
        self._max_plot_points = 500
        self._plot_total_count = 0

        # PCA9685 I²C PWM expander (optional — detected at startup)
        self.pca9685_present: bool = False
        self.pca9685_address: int = 0x40
        self.pca9685_calibrated: bool = False
        self.pca9685_osc_freq: int = 25_000_000
        self.pca9685_channels: dict[int, dict] = {}   # channel → {type, pulse_us}
        self.pca9685_last_calibration: dict | None = None  # result of last calibrate() call

        # Student map buffer — world-frame (x, y) obstacle points from robot.map_point()
        self.map_points_buf: list[tuple[float, float]] = []
        self._max_map_buf = 10_000
        self._map_total_count = 0
        self.map_pose: dict | None = None   # {x, y, heading} or None

    def clear_map(self):
        """Clear all accumulated map data (called by dashboard or student code)."""
        self.map_points_buf = []
        self._map_total_count = 0
        self.map_pose = None

    @property
    def uptime(self) -> float:
        return time.monotonic() - self._start

    def add_plot(self, label: str, value: float):
        import time as _time
        self.plot_points.append({"type": "plot", "label": label, "value": value, "ts": _time.time()})
        self._plot_total_count += 1
        if len(self.plot_points) > self._max_plot_points:
            self.plot_points = self.plot_points[-self._max_plot_points:]

    def add_log(self, level: str, message: str):
        import time as _time
        entry = {
            "type": "log",
            "level": level,
            "message": message,
            "ts": _time.time(),
        }
        self.logs.append(entry)
        self._log_total_count += 1
        if len(self.logs) > self._max_logs:
            self.logs = self.logs[-self._max_logs:]

    def get_uart_rx_deltas(self) -> dict[int, bytes]:
        """Return accumulated bytes per UART port and clear all buffers.

        Returns only ports that have data (may be empty dict).
        """
        result: dict[int, bytes] = {}
        for pid, buf in self.uart_rx_buffers.items():
            if buf:
                result[pid] = bytes(buf)
                buf.clear()
        return result

    def to_ws_message(self) -> dict:
        """Snapshot suitable for sending to WebSocket or ZMQ clients."""
        msg: dict = {
            "type": "state",
            "ts": self.rp2040_ts,
            "uptime": round(self.uptime, 1),
            "ports": dict(self.ports),
            "config_finalized": self.config_finalized,
            "rp2040_connected": self.rp2040_connected,
        }
        if self.lidar_scan is not None:
            msg["lidar"] = self.lidar_scan
        if self.map_pose is not None:
            msg["map_pose"] = self.map_pose
        msg["lidar_config"] = {
            "offset":           self.lidar_offset_deg,
            "x_offset":         self.lidar_x_offset_cm,
            "y_offset":         self.lidar_y_offset_cm,
            "max_cm":           self.lidar_max_cm,
            "code_configured":  self.lidar_code_configured,
        }
        msg["imu_mount"] = {
            "yaw":      self.imu_mount_yaw,
            "pitch":    self.imu_mount_pitch,
            "roll":     self.imu_mount_roll,
            "code_set": self.imu_mount_code_set,
        }
        msg["port_invert"]        = dict(self.port_invert)
        msg["port_invert_locked"] = list(self.port_invert_code_set)
        msg["gamepad"] = self.gamepad.to_dict()
        if self.battery_present:
            msg["battery"] = {
                "soc":     self.battery_soc,
                "voltage": self.battery_voltage,
                "chip":    self.battery_chip,
            }
        msg["pca9685"] = {
            "present":    self.pca9685_present,
            "address":    self.pca9685_address,
            "calibrated": self.pca9685_calibrated,
            "osc_freq":   self.pca9685_osc_freq,
            "channels":          {str(k): v for k, v in self.pca9685_channels.items()},
            "last_calibration":  self.pca9685_last_calibration,
        }
        return msg
