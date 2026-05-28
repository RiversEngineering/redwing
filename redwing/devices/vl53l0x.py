"""VL53L0X time-of-flight distance sensor (ST Microelectronics).

The sensor is auto-detected by the firmware at startup on the dedicated
I²C port (GP4 SDA / GP5 SCL).  No port configuration is needed in
student code.

Example::

    lidar = robot.vl53l0x()
    robot.start()

    while True:
        if lidar.valid:
            robot.log(f"Distance: {lidar.distance:.1f} cm")
        robot.sleep(0.02)
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Connection

_I2C_PORT_ID = "16"


class VL53L0X:
    """Read-only access to a VL53L0X ToF distance sensor on the I²C port.

    The sensor must be wired to **GP4 (SDA)** and **GP5 (SCL)**.  Detection
    is automatic — the firmware probes the I²C bus during startup and begins
    continuous ranging if the sensor is found.

    ``distance``, ``distance_mm``, and the other data properties raise
    :class:`RuntimeError` if the sensor is not detected.  Use
    ``lidar.connected`` to check presence without risking an exception.

    Range: ~20 mm – 2 000 mm (2 m) under good lighting conditions.
    """

    def __init__(self, conn: "Connection") -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _port(self) -> dict:
        """Return port data, raising RuntimeError if sensor is absent."""
        state = self._conn.get_all_state()
        data  = state.get("ports", {}).get(_I2C_PORT_ID)
        if data is None or data.get("type") != "vl53l0x":
            raise RuntimeError(
                "VL53L0X not detected. "
                "Check that the sensor is wired to the I²C port (GP4 SDA / GP5 SCL) "
                "and that the firmware was built with VL53L0X support."
            )
        return data

    # ------------------------------------------------------------------
    # Status (safe to call even when not connected)
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """``True`` if the VL53L0X was detected at startup and is active."""
        state = self._conn.get_all_state()
        data  = state.get("ports", {}).get(_I2C_PORT_ID)
        return data is not None and data.get("type") == "vl53l0x"

    # ------------------------------------------------------------------
    # Distance
    # ------------------------------------------------------------------

    @property
    def distance(self) -> float:
        """Distance in **centimetres**.

        Returns ``0.0`` when the target is out of range.
        Raises :class:`RuntimeError` if the sensor is not connected.

        Example::

            if lidar.valid:
                robot.log(f"{lidar.distance:.1f} cm")
        """
        d = self._port()
        if not d.get("valid", False):
            return 0.0
        return round(d.get("distance_mm", 0) / 10.0, 2)

    @property
    def distance_mm(self) -> int:
        """Distance in **millimetres**.

        Returns ``0`` when out of range.
        Raises :class:`RuntimeError` if the sensor is not connected.
        """
        return int(self._port().get("distance_mm", 0))

    @property
    def valid(self) -> bool:
        """``True`` if the most recent reading is in range and reliable.

        Does **not** raise if the sensor is disconnected — returns ``False``
        instead.  Use this to guard reads safely::

            if lidar.valid:
                stop_if_close(lidar.distance)
        """
        try:
            return bool(self._port().get("valid", False))
        except RuntimeError:
            return False
