"""IMU (inertial measurement unit) sensor support.

The firmware auto-detects one IMU on the I²C bus at startup in priority
order: BNO085, BNO055, MPU-6050.  No port configuration is needed.

Example::

    imu = robot.imu()
    robot.start()

    while True:
        robot.log(f"Heading: {imu.heading:.1f}°  Accel: {imu.acceleration}")
        robot.sleep(0.02)
"""

from __future__ import annotations
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Connection

_IMU_PORT_ID = "17"
_FUSION_TYPES = {"bno085", "bno055"}
_ALL_TYPES    = {"bno085", "bno055", "mpu6050"}


class IMU:
    """Read-only access to an auto-detected IMU on the I²C port.

    Supports **BNO085**, **BNO055** (9-axis fusion with quaternion output),
    and **MPU-6050** (6-axis accel + gyro, no fusion).

    All data properties raise :class:`RuntimeError` if no IMU was detected.
    Use :attr:`connected` and :attr:`type` to check presence first.
    """

    def __init__(self, conn: "Connection") -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _port(self) -> dict:
        state = self._conn.get_all_state()
        data  = state.get("ports", {}).get(_IMU_PORT_ID)
        if data is None or data.get("type") not in _ALL_TYPES:
            raise RuntimeError(
                "No IMU detected. "
                "Check that the sensor is wired to the I²C port (GP4 SDA / GP5 SCL)."
            )
        return data

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """``True`` if an IMU was found at startup."""
        state = self._conn.get_all_state()
        data  = state.get("ports", {}).get(_IMU_PORT_ID)
        return data is not None and data.get("type") in _ALL_TYPES

    @property
    def type(self) -> str:
        """Detected sensor type: ``"bno085"``, ``"bno055"``, or ``"mpu6050"``."""
        return self._port().get("type", "unknown")

    # ------------------------------------------------------------------
    # Orientation (fusion sensors only)
    # ------------------------------------------------------------------

    @property
    def quaternion(self) -> tuple[float, float, float, float]:
        """Orientation as a unit quaternion ``(w, x, y, z)``.

        Raises :class:`RuntimeError` if the sensor is not a fusion type
        (BNO085/BNO055) or is not connected.
        """
        data = self._port()
        if data.get("type") not in _FUSION_TYPES:
            raise RuntimeError("quaternion is only available on BNO085/BNO055")
        q = data["quaternion"]
        return (q["w"], q["x"], q["y"], q["z"])

    @property
    def heading(self) -> float:
        """Yaw angle in degrees, 0–360, where 0 is the startup heading.

        Derived from the quaternion using the standard formula::

            yaw = atan2(2*(w*z + x*y), 1 - 2*(y² + z²))

        Raises :class:`RuntimeError` for MPU-6050 (no fusion).
        """
        w, x, y, z = self.quaternion
        yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
        deg = math.degrees(yaw) % 360.0
        return round(deg, 2)

    # ------------------------------------------------------------------
    # Linear acceleration
    # ------------------------------------------------------------------

    @property
    def acceleration(self) -> tuple[float, float, float]:
        """Linear acceleration in m/s² as ``(x, y, z)``.

        For BNO085/BNO055 this is gravity-compensated linear acceleration.
        For MPU-6050 this is raw acceleration in g converted to m/s²
        (gravity included; subtract ~9.81 m/s² on the vertical axis if needed).
        """
        data = self._port()
        t = data.get("type")
        if t in _FUSION_TYPES:
            a = data["linear_acceleration"]
        else:
            # MPU-6050: raw accel in g → m/s²
            raw = data["acceleration"]
            a = {k: v * 9.80665 for k, v in raw.items()}
        return (round(a["x"], 4), round(a["y"], 4), round(a["z"], 4))

    # ------------------------------------------------------------------
    # Gyroscope (MPU-6050 only)
    # ------------------------------------------------------------------

    @property
    def gyro(self) -> tuple[float, float, float]:
        """Angular rate in °/s as ``(x, y, z)``.

        Only available on MPU-6050.  Raises :class:`RuntimeError` on
        BNO085/BNO055 (use :attr:`quaternion` or :attr:`heading` instead).
        """
        data = self._port()
        if data.get("type") != "mpu6050":
            raise RuntimeError("gyro is only available on MPU-6050")
        g = data["gyro"]
        return (round(g["x"], 4), round(g["y"], 4), round(g["z"], 4))
