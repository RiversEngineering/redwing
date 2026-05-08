"""Shared in-memory state for the daemon.

All subsystems read/write this single object. Access is protected by an
asyncio.Lock — always use ``async with state.lock`` before modifying.
"""

import asyncio
import time
from typing import Any


class SharedState:
    def __init__(self):
        self.lock = asyncio.Lock()
        self._start = time.monotonic()

        # Latest data from RP2040
        self.rp2040_ts: int = 0           # RP2040 millisecond timestamp
        self.ports: dict[str, Any] = {}   # port_id → port data dict

        # Port configuration metadata (set by IPC handler on CONFIGURE)
        self.port_config: dict[str, str] = {}   # port_id → type string

        # Encoder → motor attachment map (motor_port → encoder_port)
        self.encoder_map: dict[int, int] = {}

        # PID target velocities for closed-loop motors (port_id → ticks/s × 10)
        self.target_velocities: dict[int, float] = {}

        # UART RX bytes received from RP2040 UART0 (S0/S1), accumulated between broadcasts
        self.uart_rx_buffer: bytearray = bytearray()

        # Latest LIDAR scan: list of (angle_deg, distance_cm) tuples, or None
        self.lidar_scan: list | None = None

        # Latest camera frame as JPEG bytes (None = no camera)
        self.camera_frame: bytes | None = None
        # If student called camera_show(frame), this holds the override frame
        self.camera_override: bytes | None = None
        self.show_raw: bool = True   # True = show live feed; False = show override

        # Log buffer for the dashboard (newest last)
        self.logs: list[dict] = []
        self._max_logs = 500

    @property
    def uptime(self) -> float:
        return time.monotonic() - self._start

    def add_log(self, level: str, message: str):
        import time as _time
        entry = {
            "type": "log",
            "level": level,
            "message": message,
            "ts": _time.time(),
        }
        self.logs.append(entry)
        if len(self.logs) > self._max_logs:
            self.logs = self.logs[-self._max_logs:]

    def get_uart_rx_delta(self) -> bytes:
        """Return accumulated UART RX bytes and clear the buffer."""
        data = bytes(self.uart_rx_buffer)
        self.uart_rx_buffer = bytearray()
        return data

    def to_ws_message(self) -> dict:
        """Snapshot suitable for sending to WebSocket or ZMQ clients."""
        msg: dict = {
            "type": "state",
            "ts": self.rp2040_ts,
            "uptime": round(self.uptime, 1),
            "ports": dict(self.ports),
        }
        if self.lidar_scan is not None:
            msg["lidar"] = self.lidar_scan
        return msg
