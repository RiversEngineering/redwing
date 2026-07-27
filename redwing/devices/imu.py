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
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Connection

_IMU_PORT_ID  = "17"
_FUSION_TYPES = {"bno085", "bno055"}
_ALL_TYPES    = {"bno085", "bno055", "mpu6050"}

# ---------------------------------------------------------------------------
# Quaternion helpers (module-level for use in odometry too)
# ---------------------------------------------------------------------------

def _euler_to_quat(yaw_deg: float, pitch_deg: float, roll_deg: float) -> tuple:
    """ZYX Euler angles → unit quaternion (w, x, y, z)."""
    y = math.radians(yaw_deg)   / 2
    p = math.radians(pitch_deg) / 2
    r = math.radians(roll_deg)  / 2
    cy, sy = math.cos(y), math.sin(y)
    cp, sp = math.cos(p), math.sin(p)
    cr, sr = math.cos(r), math.sin(r)
    return (
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    )


def _qmul(q1: tuple, q2: tuple) -> tuple:
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return (
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    )


def _qconj(q: tuple) -> tuple:
    w, x, y, z = q
    return (w, -x, -y, -z)


def _rotate_vec(q: tuple, vx: float, vy: float, vz: float) -> tuple:
    """Rotate vector by quaternion: q ⊗ (0,v) ⊗ q*."""
    _, rx, ry, rz = _qmul(_qmul(q, (0.0, vx, vy, vz)), _qconj(q))
    return (rx, ry, rz)


class IMU:
    """Read-only access to an auto-detected IMU on the I²C port.

    Supports **BNO085**, **BNO055** (9-axis fusion with quaternion output),
    and **MPU-6050** (6-axis accel + gyro, no fusion).

    All data properties raise :class:`RuntimeError` if no IMU was detected.
    Use :attr:`connected` and :attr:`type` to check presence first.
    """

    def __init__(self, conn: "Connection") -> None:
        self._conn = conn
        # Gyro-integrated heading for MPU-6050 (stateful; lock protects concurrent access)
        self._gyro_hdg:    float        = 0.0
        self._gyro_t:      float | None = None
        self._gyro_lock:   threading.Lock = threading.Lock()
        self._drift_warned: bool        = False
        # Mount rotation: q_mount describes how the sensor frame relates to the robot frame.
        # All outputs are corrected by q_mount_inv so they are expressed in robot frame.
        self._mount_q: tuple = (1.0, 0.0, 0.0, 0.0)  # identity

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
    # Mount rotation
    # ------------------------------------------------------------------

    def set_mount_rotation(
        self,
        *,
        yaw: float   = 0.0,
        pitch: float = 0.0,
        roll: float  = 0.0,
    ) -> None:
        """Specify the IMU's physical mounting orientation on the robot.

        All heading, quaternion, and acceleration values are automatically
        corrected so they are expressed in the robot's reference frame
        regardless of how the sensor is physically oriented.

        The robot frame axes are:

        - **+X** forward (the direction the robot faces)
        - **+Y** left
        - **+Z** up

        Parameters
        ----------
        yaw:
            Rotation around +Z (vertical) in degrees, positive = CCW from
            above.  **Most common** — use this when the IMU PCB is rotated
            flat on the robot deck.
        pitch:
            Rotation around +Y (lateral) in degrees.
            Use when the IMU is tilted forward or backward.
        roll:
            Rotation around +X (forward) in degrees.
            Use when the IMU is mounted on its side or upside-down.

        Examples::

            # IMU rotated 90° clockwise on the robot deck
            imu.set_mount_rotation(yaw=-90)

            # IMU mounted upside-down (flipped over)
            imu.set_mount_rotation(roll=180)

            # IMU mounted with USB port facing left, board flat
            imu.set_mount_rotation(yaw=90)
        """
        self._mount_q = _euler_to_quat(yaw, pitch, roll)

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
        """Orientation as a unit quaternion ``(w, x, y, z)`` in robot frame.

        Mount rotation is applied automatically — the result always reflects
        the robot's orientation regardless of how the IMU is physically
        positioned.

        Raises :class:`RuntimeError` if the sensor is not a fusion type
        (BNO085/BNO055) or is not connected.
        """
        data = self._port()
        if data.get("type") not in _FUSION_TYPES:
            raise RuntimeError("quaternion is only available on BNO085/BNO055")
        q = data["quaternion"]
        q_sensor = (q["w"], q["x"], q["y"], q["z"])
        w, x, y, z = _qmul(_qconj(self._mount_q), q_sensor)
        return (round(w, 6), round(x, 6), round(y, 6), round(z, 6))

    @property
    def heading(self) -> float:
        """Yaw angle in degrees (0–360) in robot frame.

        0° is the robot's heading at startup.  Mount rotation is applied
        automatically.

        **BNO085 / BNO055**: derived from the fused quaternion — stable and
        drift-free over long runs::

            yaw = atan2(2*(w*z + x*y), 1 - 2*(y² + z²))

        **MPU-6050**: integrated from the gyroscope Z axis.  Accurate for
        short durations (seconds to a few minutes); drifts slowly over time
        because there is no magnetometer to correct it.  Call
        :meth:`reset_heading` to re-zero after repositioning the robot.

        Positive heading = counter-clockwise rotation (standard math convention).
        """
        data = self._port()
        if data.get("type") in _FUSION_TYPES:
            q = data["quaternion"]
            q_sensor = (q["w"], q["x"], q["y"], q["z"])
            qw, qx, qy, qz = _qmul(_qconj(self._mount_q), q_sensor)
            yaw = math.atan2(
                2.0 * (qw * qz + qx * qy),
                1.0 - 2.0 * (qy * qy + qz * qz),
            )
            return round(math.degrees(yaw) % 360.0, 2)
        # MPU-6050: integrate gyro Z at call rate
        if not self._drift_warned:
            self._drift_warned = True
            import warnings
            warnings.warn(
                "MPU-6050 heading uses gyro integration and drifts over time "
                "(typically 0.5–2° per minute). For reliable long-term heading "
                "use a BNO085 or BNO055. Call imu.reset_heading() to re-zero "
                "after the robot has been repositioned.",
                stacklevel=2,
            )
        g = data["gyro"]
        gx, gy, gz = g["x"], g["y"], g["z"]
        # Rotate the full gyro vector into the robot frame so that heading
        # integrates robot-yaw correctly for any IMU mounting orientation.
        _, _, gz_robot = _rotate_vec(_qconj(self._mount_q), gx, gy, gz)
        now = time.monotonic()
        with self._gyro_lock:
            if self._gyro_t is not None:
                dt = now - self._gyro_t
                self._gyro_hdg = (self._gyro_hdg + gz_robot * dt) % 360.0
            self._gyro_t = now
            return round(self._gyro_hdg, 2)

    def reset_heading(self, heading_deg: float = 0.0) -> None:
        """Reset the gyro-integrated heading to *heading_deg* (MPU-6050 only).

        Has no effect on BNO085/BNO055 — their heading is always relative to
        the orientation at firmware boot.

        Example::

            imu.reset_heading()        # re-zero at current position
            imu.reset_heading(90.0)    # declare current orientation as 90°
        """
        with self._gyro_lock:
            self._gyro_hdg = float(heading_deg) % 360.0
            self._gyro_t   = None  # discard accumulated interval

    # ------------------------------------------------------------------
    # Linear acceleration
    # ------------------------------------------------------------------

    @property
    def acceleration(self) -> tuple[float, float, float]:
        """Linear acceleration in m/s² as ``(x, y, z)`` in robot frame.

        Mount rotation is applied automatically.

        For BNO085/BNO055 this is gravity-compensated linear acceleration.
        For MPU-6050 this is raw acceleration in g converted to m/s²
        (gravity included; subtract ~9.81 m/s² on the vertical axis if needed).
        """
        data = self._port()
        t = data.get("type")
        if t in _FUSION_TYPES:
            a = data["linear_acceleration"]
        else:
            raw = data["acceleration"]
            a = {k: v * 9.80665 for k, v in raw.items()}
        ax, ay, az = a["x"], a["y"], a["z"]
        if self._mount_q != (1.0, 0.0, 0.0, 0.0):
            ax, ay, az = _rotate_vec(_qconj(self._mount_q), ax, ay, az)
        return (round(ax, 4), round(ay, 4), round(az, 4))

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
