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

        # Latest camera frame as JPEG bytes (seeded with placeholder by CameraCapture)
        self.camera_frame: bytes | None = None
        self.camera_frame_b64: str = ""   # base64-encoded version for student library
        # If student called camera_show(frame), this holds the override frame
        self.camera_override: bytes | None = None
        self.show_raw: bool = True   # True = show live feed; False = show override

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
        }
        if self.lidar_scan is not None:
            msg["lidar"] = self.lidar_scan
        msg["gamepad"] = self.gamepad.to_dict()
        return msg
