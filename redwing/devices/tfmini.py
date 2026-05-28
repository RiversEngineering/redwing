"""TFMini and TFLuna time-of-flight LiDAR sensors (Benewake UART frame protocol).

Both sensors output a continuous stream of 9-byte frames at up to 100 Hz:

  Byte 0:   0x59  (frame header)
  Byte 1:   0x59  (frame header)
  Byte 2:   distance low byte    (centimetres)
  Byte 3:   distance high byte
  Byte 4:   signal strength low byte
  Byte 5:   signal strength high byte
  Byte 6:   reserved (TFMini) / temperature low byte × 100 (TFLuna)
  Byte 7:   reserved (TFMini) / temperature high byte × 100 (TFLuna)
  Byte 8:   checksum = lower 8 bits of sum of bytes 0–7

Wire the sensor TX pin to the Redwing board RX pin and vice versa.
D7 (GP12=RX, GP13=TX) or D6 (GP24=RX, GP25=TX) can be used.

Default baud rate for both sensors is 115200.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Connection

_FRAME_LEN = 9
_HEADER    = (0x59, 0x59)
_MIN_STRENGTH = 100   # readings below this are considered unreliable


class _TFBase:
    """Shared frame-parsing logic for TFMini and TFLuna."""

    def __init__(self, conn: "Connection") -> None:
        self._conn     = conn
        self._buf      = bytearray()
        self._dist_cm: int | None  = None
        self._strength: int | None = None
        self._raw_temp: int | None = None

    def _ingest(self) -> None:
        """Pull new bytes from the UART buffer and parse any complete frames."""
        new = self._conn.read_uart_bytes()
        if new:
            self._buf.extend(new)

        while len(self._buf) >= _FRAME_LEN:
            # Sync: scan for 0x59 0x59 header
            if self._buf[0] != _HEADER[0] or self._buf[1] != _HEADER[1]:
                del self._buf[0]
                continue

            frame = self._buf[:_FRAME_LEN]
            if (sum(frame[:8]) & 0xFF) != frame[8]:
                # Bad checksum — skip one byte and re-sync
                del self._buf[0]
                continue

            self._dist_cm  = frame[2] | (frame[3] << 8)
            self._strength = frame[4] | (frame[5] << 8)
            self._raw_temp = frame[6] | (frame[7] << 8)
            del self._buf[:_FRAME_LEN]

    # ── Public properties ────────────────────────────────────────────────

    @property
    def distance(self) -> float | None:
        """Distance to target in **centimetres**.

        Returns ``None`` until the first valid frame is received.
        Returns ``0.0`` when the target is out of range or too close.

        Example::

            d = lidar.distance
            if d is not None and d < 30:
                robot.stop()
        """
        self._ingest()
        return float(self._dist_cm) if self._dist_cm is not None else None

    @property
    def distance_m(self) -> float | None:
        """Distance to target in **metres** (``None`` until first frame)."""
        d = self.distance
        return d / 100.0 if d is not None else None

    @property
    def strength(self) -> int | None:
        """Signal strength of the last measurement.

        Higher values indicate a more reliable reading.  Typical range is
        0–65535; values below ~100 suggest the reading should be treated
        with caution.  Returns ``None`` until the first frame is received.
        """
        self._ingest()
        return self._strength

    @property
    def valid(self) -> bool:
        """``True`` when a reading has been received and the signal looks reliable.

        Checks that distance > 0 and strength > 100.  Use this to guard
        against out-of-range or low-confidence readings::

            if lidar.valid:
                robot.log(f"Distance: {lidar.distance:.1f} cm")
        """
        self._ingest()
        if self._dist_cm is None or self._strength is None:
            return False
        return self._dist_cm > 0 and self._strength >= _MIN_STRENGTH


class TFMini(_TFBase):
    """Benewake TFMini time-of-flight LiDAR sensor.

    Range: ~0.3 – 1200 cm.  Default baud: 115200.

    Wire to **D7** (default) or **D6**, then obtain via ``robot.tfmini()``::

        lidar = robot.tfmini()          # D7, 115200 baud
        # or: lidar = robot.tfmini(port=14)  # D6

        robot.start()

        while True:
            if lidar.valid:
                robot.log(f"Distance: {lidar.distance:.1f} cm")
            robot.sleep(0.02)
    """


class TFLuna(_TFBase):
    """Benewake TFLuna time-of-flight LiDAR sensor.

    Range: ~0.2 – 800 cm.  Default baud: 115200.
    Provides distance, signal strength, and chip temperature.

    Wire to **D7** (default) or **D6**, then obtain via ``robot.tfluna()``::

        lidar = robot.tfluna()          # D7, 115200 baud

        robot.start()

        while True:
            if lidar.valid:
                robot.log(f"{lidar.distance:.1f} cm  {lidar.temperature:.1f} °C")
            robot.sleep(0.02)
    """

    @property
    def temperature(self) -> float | None:
        """Sensor chip temperature in **°C** (``None`` until first frame).

        The TFLuna encodes temperature as (raw / 100.0) °C.
        Note: this is the *chip* temperature, not ambient air temperature.
        """
        self._ingest()
        if self._raw_temp is None:
            return None
        return self._raw_temp / 100.0
