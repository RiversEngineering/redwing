"""Dead-reckoning odometry and drive control.

Provides :class:`DifferentialDrive` and :class:`MecanumDrive` — objects that
track a 2-D robot pose using encoder counts fused with an optional IMU heading,
and expose blocking movement commands for dead-reckoning navigation.

Quick start — differential drive::

    robot = redwing.Robot()

    lm = robot.motor(robot.D0)
    rm = robot.motor(robot.D1)
    rm.inverted = True          # flip right motor if it spins backwards

    le = robot.encoder(robot.D2)
    re = robot.encoder(robot.D3)
    imu = robot.imu()           # optional but strongly recommended

    drive = robot.differential_drive(
        left_motor=lm,   right_motor=rm,
        left_encoder=le, right_encoder=re,
        imu=imu,
        wheel_diameter_mm=60,
        track_width_mm=150,
        ticks_per_rev=1440,
    )
    robot.start()

    drive.forward(0.5)      # 0.5 m forward
    drive.turn_right(90)    # 90° clockwise
    print(drive.pose)       # (x_m, y_m, heading_deg)

Quick start — mecanum drive::

    drive = robot.mecanum_drive(
        fl=(fl_motor, fl_enc),
        fr=(fr_motor, fr_enc),
        bl=(bl_motor, bl_enc),
        br=(br_motor, br_enc),
        wheel_diameter_mm=100,
        track_width_mm=300,
        wheelbase_mm=280,
        ticks_per_rev=1440,
    )
    robot.start()

    drive.forward(0.5)
    drive.strafe_right(0.3)
    drive.rotate(-90)       # 90° counter-clockwise
    drive.strafe(0.4, 45)   # move diagonally at 45° (forward-right)

Coordinate frame
----------------
The robot uses a right-hand coordinate system:

- ``+X``: forward (the direction the robot faces at startup)
- ``+Y``: left
- ``+Z``: up
- ``heading``: rotation around +Z, degrees, 0 at startup.
  **Positive = counter-clockwise** (left turn), consistent with
  ``imu.heading``.  Use :meth:`turn_left` / :meth:`turn_right` to avoid
  thinking about sign conventions.

The ``imu.acceleration`` vector and ``imu.quaternion`` are expressed in the
same robot frame once :meth:`~redwing.devices.imu.IMU.set_mount_rotation`
has been called.

Heading note
~~~~~~~~~~~~
The IMU heading (0–360°, increasing = CCW from above) matches the mathematical
convention.  If your robot turns the wrong direction for a given command,
set ``motor.inverted = True`` on the relevant motor(s).
"""

from __future__ import annotations

import math
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .devices.motor import Motor
    from .devices.encoder import Encoder
    from .devices.imu import IMU

# ── Internal constants ──────────────────────────────────────────────────────────

_ODOM_HZ   = 50          # odometry update rate (Hz)
_ODOM_DT   = 1.0 / _ODOM_HZ
_RAMP_FRAC = 0.25        # slow down in the last 25% of travel
_MIN_PWR   = 20.0        # minimum power during ramp-down
_DIST_TOL  = 0.01        # 1 cm positional tolerance
_ANG_TOL   = 1.5         # 1.5° angular tolerance

# ── Angle helpers ───────────────────────────────────────────────────────────────

def _wrap(deg: float) -> float:
    """Wrap angle to (−180, 180]."""
    return (deg + 180.0) % 360.0 - 180.0


def _hdiff(new_deg: float, old_deg: float) -> float:
    """Signed shortest-arc difference (new − old), clamped to (−180, 180]."""
    return _wrap(new_deg - old_deg)


# ── DifferentialDrive ───────────────────────────────────────────────────────────

class DifferentialDrive:
    """Two-wheel differential drive with odometry and dead-reckoning movement.

    Parameters
    ----------
    left_motor, right_motor:
        :class:`~redwing.devices.motor.Motor` objects (created with
        ``robot.motor()``).  If a motor spins backwards, set
        ``motor.inverted = True`` rather than using the ``invert_*`` flags.
    left_encoder, right_encoder:
        :class:`~redwing.devices.encoder.Encoder` objects (``robot.encoder()``).
    imu:
        Optional BNO085/BNO055 :class:`~redwing.devices.imu.IMU`.  When
        provided the heading is taken directly from the IMU instead of being
        derived from wheel speeds, which greatly reduces angular drift.
    wheel_diameter_mm:
        Diameter of the drive wheels in millimetres.
    track_width_mm:
        Centre-to-centre distance between the left and right wheels (mm).
    ticks_per_rev:
        Encoder pulses per full wheel revolution (after any gearing).
    invert_left / invert_right:
        Flip the sign of one encoder's delta.  Only needed when the encoder
        is mounted on the *opposite* side of a gearbox from the wheel.
    """

    def __init__(
        self,
        *,
        left_motor:    "Motor",
        right_motor:   "Motor",
        left_encoder:  "Encoder",
        right_encoder: "Encoder",
        imu:           "IMU | None" = None,
        wheel_diameter_mm: float,
        track_width_mm:    float,
        ticks_per_rev:     int,
        invert_left:  bool = False,
        invert_right: bool = False,
        robot=None,
    ):
        self._lm   = left_motor
        self._rm   = right_motor
        self._le   = left_encoder
        self._re   = right_encoder
        self._imu  = imu
        self._mpt  = math.pi * wheel_diameter_mm / 1000.0 / ticks_per_rev
        self._track = track_width_mm / 1000.0
        self._il   = invert_left
        self._ir   = invert_right
        self._robot = robot

        self._x       = 0.0
        self._y       = 0.0
        self._heading = 0.0   # degrees, CCW positive

        self._last_l:    int   = 0
        self._last_r:    int   = 0
        self._last_hdg:  float | None = None
        self._imu_is_mpu = False

        self._lock    = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def _start(self):
        """Begin background odometry.  Called automatically by robot.start()."""
        self._last_l = self._le.count
        self._last_r = self._re.count
        if self._imu and self._imu.connected:
            self._imu_is_mpu = (self._imu.type == "mpu6050")
            self._last_hdg   = self._imu.heading
            if self._imu_is_mpu and self._robot is not None:
                self._robot.log(
                    "⚠ MPU-6050 heading uses gyro integration and drifts over time "
                    "(typically 0.5–2° per minute). For reliable odometry use a "
                    "BNO085 or BNO055. Call drive.reset_pose() to re-zero after "
                    "repositioning.",
                    level="warning",
                )
        else:
            self._imu_is_mpu = False
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True,
                                         name="diff-odom")
        self._thread.start()

    def _loop(self):
        while self._running:
            t0 = time.monotonic()
            self._tick()
            rem = _ODOM_DT - (time.monotonic() - t0)
            if rem > 0:
                time.sleep(rem)

    def _tick(self):
        lc = self._le.count
        rc = self._re.count
        dl = (lc - self._last_l) * self._mpt * (-1 if self._il else 1)
        dr = (rc - self._last_r) * self._mpt * (-1 if self._ir else 1)
        self._last_l = lc
        self._last_r = rc

        d = (dl + dr) * 0.5  # net forward displacement this tick

        if self._imu and self._imu.connected and self._last_hdg is not None:
            if self._imu_is_mpu:
                # MPU-6050: integrate gyro Z directly at the known loop rate.
                # Bypasses imu.heading to avoid call-timing jitter in the
                # stateful integrator and gives cleaner 50 Hz integration.
                gz   = self._imu.gyro[2]          # °/s, CCW positive
                dhdg = gz * _ODOM_DT
                self._last_hdg = (self._last_hdg + dhdg) % 360.0
            else:
                # BNO085/BNO055: use absolute fused heading — no drift.
                new_hdg        = self._imu.heading
                dhdg           = _hdiff(new_hdg, self._last_hdg)
                self._last_hdg = new_hdg
        else:
            # No IMU: derive heading from wheel speed difference.
            # dl - dr > 0 when left wheel moves more → CCW → positive dhdg.
            dhdg = math.degrees((dl - dr) / self._track)  # CCW positive

        with self._lock:
            self._heading = (self._heading + dhdg) % 360.0
            h_rad = math.radians(self._heading)
            self._x += d * math.cos(h_rad)
            self._y += d * math.sin(h_rad)
            x, y, hdg = self._x, self._y, self._heading

        if self._robot is not None:
            self._robot.map_pose(x * 100.0, y * 100.0, hdg)

    # ── Pose ───────────────────────────────────────────────────────────────────

    @property
    def x(self) -> float:
        """X position in metres (positive = forward from start)."""
        with self._lock:
            return self._x

    @property
    def y(self) -> float:
        """Y position in metres (positive = left from start)."""
        with self._lock:
            return self._y

    @property
    def heading(self) -> float:
        """Heading in degrees (0 = startup, positive = counter-clockwise)."""
        with self._lock:
            return self._heading

    @property
    def pose(self) -> tuple[float, float, float]:
        """Current pose as ``(x_m, y_m, heading_deg)``."""
        with self._lock:
            return (self._x, self._y, self._heading)

    def reset_pose(self, x: float = 0.0, y: float = 0.0,
                   heading_deg: float = 0.0) -> None:
        """Reset the estimated pose to the given values."""
        with self._lock:
            self._x       = float(x)
            self._y       = float(y)
            self._heading = float(heading_deg) % 360.0
        if self._imu and self._imu.connected:
            self._last_hdg = self._imu.heading

    def correct_pose(self, x: float, y: float,
                     heading_deg: float | None = None) -> None:
        """Apply an external pose correction and continue integrating from there.

        Use this to snap the odometry to a known-good position fix from an
        external source (AprilTag, field beacon, etc.).

        Parameters
        ----------
        x, y:
            New position in metres.
        heading_deg:
            New heading in degrees.  Pass ``None`` to keep the current heading.
        """
        with self._lock:
            self._x = float(x)
            self._y = float(y)
            if heading_deg is not None:
                self._heading = float(heading_deg) % 360.0

    # ── Continuous drive ───────────────────────────────────────────────────────

    def drive(self, forward: float, turn: float = 0.0) -> None:
        """Set continuous drive powers (non-blocking).

        Parameters
        ----------
        forward:
            Forward / backward power, −100 to +100.
        turn:
            Turning power.  Positive = **left (CCW)**, negative = right (CW).
            The two sides are mixed as ``left = forward − turn``,
            ``right = forward + turn``.
        """
        l = max(-100.0, min(100.0, forward - turn))
        r = max(-100.0, min(100.0, forward + turn))
        self._lm.set_power(l)
        self._rm.set_power(r)

    def stop(self) -> None:
        """Stop both drive motors immediately."""
        self._lm.set_power(0)
        self._rm.set_power(0)

    # ── Dead-reckoning linear moves ────────────────────────────────────────────

    def forward(self, distance_m: float, power: float = 50.0) -> None:
        """Move forward by *distance_m* metres, then stop.

        Power ramps down in the final 25% of travel for smoother stopping.
        """
        self._linear_move(abs(distance_m), abs(power))

    def backward(self, distance_m: float, power: float = 50.0) -> None:
        """Move backward by *distance_m* metres, then stop."""
        self._linear_move(abs(distance_m), -abs(power))

    def _linear_move(self, dist_m: float, power: float) -> None:
        start_l  = self._le.count
        start_r  = self._re.count
        ramp_start = dist_m * (1.0 - _RAMP_FRAC)
        self.drive(power)
        while True:
            dl       = abs(self._le.count - start_l) * self._mpt
            dr       = abs(self._re.count - start_r) * self._mpt
            traveled = (dl + dr) * 0.5
            if traveled >= dist_m - _DIST_TOL:
                break
            if traveled > ramp_start:
                frac = max(0.0, (dist_m - traveled) / (dist_m * _RAMP_FRAC))
                p    = max(_MIN_PWR, abs(power) * frac)
                self.drive(p if power > 0 else -p)
            time.sleep(0.02)
        self.stop()

    # ── Dead-reckoning rotation ────────────────────────────────────────────────

    def rotate(self, angle_deg: float, power: float = 40.0) -> None:
        """Rotate in place by *angle_deg* degrees.

        Positive angle = **counter-clockwise** (left turn).
        Negative angle = **clockwise** (right turn).

        For clearer code prefer :meth:`turn_left` / :meth:`turn_right`.
        """
        pwr  = abs(power)
        sign = 1.0 if angle_deg >= 0 else -1.0   # +1 = CCW

        if self._imu and self._imu.connected:
            start = self._imu.heading
            self.drive(0.0, sign * pwr)
            while True:
                turned    = _hdiff(self._imu.heading, start)  # CCW positive
                remaining = angle_deg - turned                 # same sign as angle_deg
                if abs(remaining) <= _ANG_TOL:
                    break
                if abs(remaining) < 20.0:
                    p = max(15.0, pwr * abs(remaining) / 20.0)
                    self.drive(0.0, sign * p)
                time.sleep(0.02)
        else:
            arc      = math.radians(abs(angle_deg)) * self._track * 0.5
            start_l  = self._le.count
            start_r  = self._re.count
            # CCW: right wheel faster → right forward, left backward → drive(0, +)
            # CW:  left wheel faster  → left forward, right backward → drive(0, -)
            self.drive(0.0, sign * pwr)
            while True:
                dl       = abs(self._le.count - start_l) * self._mpt
                dr       = abs(self._re.count - start_r) * self._mpt
                traveled = (dl + dr) * 0.5
                if traveled >= arc - _DIST_TOL:
                    break
                time.sleep(0.02)

        self.stop()

    def turn_left(self, angle_deg: float, power: float = 40.0) -> None:
        """Turn left (counter-clockwise) by *angle_deg* degrees."""
        self.rotate(abs(angle_deg), power)

    def turn_right(self, angle_deg: float, power: float = 40.0) -> None:
        """Turn right (clockwise) by *angle_deg* degrees."""
        self.rotate(-abs(angle_deg), power)

    # ── Strafe guard ───────────────────────────────────────────────────────────

    def strafe_left(self, *_a, **_kw):
        raise NotImplementedError(
            "Differential drive cannot strafe. Use MecanumDrive for sideways movement."
        )

    def strafe_right(self, *_a, **_kw):
        raise NotImplementedError(
            "Differential drive cannot strafe. Use MecanumDrive for sideways movement."
        )

    def strafe(self, *_a, **_kw):
        raise NotImplementedError(
            "Differential drive cannot strafe. Use MecanumDrive for sideways movement."
        )


# ── MecanumDrive ────────────────────────────────────────────────────────────────

class MecanumDrive:
    """Four-wheel mecanum (holonomic) drive with odometry and dead-reckoning.

    Wheel positions and standard roller orientation::

        FL (/45°)    FR (\\45°)
        BL (\\45°)   BR (/45°)

    Motor mixing (vx = forward, vy = right, ω = CCW rotation — all as %)::

        FL = vx + vy − ω
        FR = vx − vy + ω
        BL = vx − vy − ω
        BR = vx + vy + ω

    where ``vy > 0`` strafes **right** and ``ω > 0`` turns **counter-clockwise**.

    Parameters
    ----------
    fl, fr, bl, br:
        Each is a ``(Motor, Encoder)`` tuple for that corner, e.g.::

            fl=(robot.motor(robot.D0), robot.encoder(robot.S0))

    imu:
        Optional BNO085/BNO055 IMU for heading fusion.
    wheel_diameter_mm:
        Mecanum wheel diameter in mm.
    track_width_mm:
        Distance between left-side and right-side wheel contact patches (mm).
    wheelbase_mm:
        Distance between front and rear wheel contact patches (mm).
    ticks_per_rev:
        Encoder pulses per wheel revolution.
    invert_fl / invert_fr / invert_bl / invert_br:
        Flip individual encoder signs (see :class:`DifferentialDrive` note).
    """

    def __init__(
        self,
        *,
        fl: tuple["Motor", "Encoder"],
        fr: tuple["Motor", "Encoder"],
        bl: tuple["Motor", "Encoder"],
        br: tuple["Motor", "Encoder"],
        imu:               "IMU | None" = None,
        wheel_diameter_mm: float,
        track_width_mm:    float,
        wheelbase_mm:      float,
        ticks_per_rev:     int,
        invert_fl: bool = False,
        invert_fr: bool = False,
        invert_bl: bool = False,
        invert_br: bool = False,
        robot=None,
    ):
        self._motors  = (fl[0], fr[0], bl[0], br[0])
        self._encs    = (fl[1], fr[1], bl[1], br[1])
        self._inverts = (invert_fl, invert_fr, invert_bl, invert_br)
        self._imu     = imu
        self._mpt     = math.pi * wheel_diameter_mm / 1000.0 / ticks_per_rev
        self._track   = track_width_mm / 1000.0
        self._wb      = wheelbase_mm / 1000.0
        # Rotation radius = (track + wheelbase) / 4
        self._rk      = (self._track + self._wb) * 0.25
        self._robot   = robot

        self._x       = 0.0
        self._y       = 0.0
        self._heading = 0.0

        self._last_counts: list[int]   = [0, 0, 0, 0]
        self._last_hdg:    float | None = None
        self._imu_is_mpu = False

        self._lock    = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def _start(self):
        """Begin background odometry.  Called automatically by robot.start()."""
        self._last_counts = [enc.count for enc in self._encs]
        if self._imu and self._imu.connected:
            self._imu_is_mpu = (self._imu.type == "mpu6050")
            self._last_hdg   = self._imu.heading
            if self._imu_is_mpu and self._robot is not None:
                self._robot.log(
                    "⚠ MPU-6050 heading uses gyro integration and drifts over time "
                    "(typically 0.5–2° per minute). For reliable odometry use a "
                    "BNO085 or BNO055. Call drive.reset_pose() to re-zero after "
                    "repositioning.",
                    level="warning",
                )
        else:
            self._imu_is_mpu = False
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True,
                                         name="mecanum-odom")
        self._thread.start()

    def _loop(self):
        while self._running:
            t0 = time.monotonic()
            self._tick()
            rem = _ODOM_DT - (time.monotonic() - t0)
            if rem > 0:
                time.sleep(rem)

    def _tick(self):
        counts = [enc.count for enc in self._encs]
        ds     = [
            (counts[i] - self._last_counts[i]) * self._mpt * (-1 if self._inverts[i] else 1)
            for i in range(4)
        ]
        self._last_counts = counts

        fl, fr, bl, br = ds
        # Robot-frame displacement (forward = x, right = y in robot frame)
        dx_r = (fl + fr + bl + br) * 0.25
        dy_r = (fl - fr - bl + br) * 0.25   # right positive

        if self._imu and self._imu.connected and self._last_hdg is not None:
            if self._imu_is_mpu:
                gz             = self._imu.gyro[2]
                dhdg           = gz * _ODOM_DT
                self._last_hdg = (self._last_hdg + dhdg) % 360.0
            else:
                new_hdg        = self._imu.heading
                dhdg           = _hdiff(new_hdg, self._last_hdg)
                self._last_hdg = new_hdg
        else:
            dhdg = math.degrees((-fl + fr - bl + br) / (4.0 * self._rk))  # CCW positive

        with self._lock:
            self._heading = (self._heading + dhdg) % 360.0
            h_rad  = math.radians(self._heading)
            cos_h, sin_h = math.cos(h_rad), math.sin(h_rad)
            # Transform robot frame (x=fwd, y=right) → world frame (x=fwd, y=left)
            self._x += dx_r * cos_h + dy_r * sin_h
            self._y += dx_r * sin_h - dy_r * cos_h
            x, y, hdg = self._x, self._y, self._heading

        if self._robot is not None:
            self._robot.map_pose(x * 100.0, y * 100.0, hdg)

    # ── Pose ───────────────────────────────────────────────────────────────────

    @property
    def x(self) -> float:
        """X position in metres (positive = forward from start)."""
        with self._lock: return self._x

    @property
    def y(self) -> float:
        """Y position in metres (positive = left from start)."""
        with self._lock: return self._y

    @property
    def heading(self) -> float:
        """Heading in degrees (0 = startup, positive = counter-clockwise)."""
        with self._lock: return self._heading

    @property
    def pose(self) -> tuple[float, float, float]:
        """Current pose as ``(x_m, y_m, heading_deg)``."""
        with self._lock: return (self._x, self._y, self._heading)

    def reset_pose(self, x: float = 0.0, y: float = 0.0,
                   heading_deg: float = 0.0) -> None:
        """Reset the estimated pose."""
        with self._lock:
            self._x       = float(x)
            self._y       = float(y)
            self._heading = float(heading_deg) % 360.0
        if self._imu and self._imu.connected:
            self._last_hdg = self._imu.heading

    def correct_pose(self, x: float, y: float,
                     heading_deg: float | None = None) -> None:
        """Apply an external pose correction (AprilTag, beacon, etc.)."""
        with self._lock:
            self._x = float(x)
            self._y = float(y)
            if heading_deg is not None:
                self._heading = float(heading_deg) % 360.0

    # ── Continuous drive ───────────────────────────────────────────────────────

    def move(self, vx: float, vy: float = 0.0, omega: float = 0.0) -> None:
        """Set continuous drive powers (non-blocking).

        Parameters
        ----------
        vx:
            Forward / backward power, −100 to +100.
        vy:
            Strafe power.  Positive = **right**, negative = left.
        omega:
            Rotation power.  Positive = **counter-clockwise** (left), negative = CW.
        """
        fl = vx + vy - omega
        fr = vx - vy + omega
        bl = vx - vy - omega
        br = vx + vy + omega
        mx = max(abs(fl), abs(fr), abs(bl), abs(br), 100.0)
        s  = 100.0 / mx
        self._motors[0].set_power(fl * s)
        self._motors[1].set_power(fr * s)
        self._motors[2].set_power(bl * s)
        self._motors[3].set_power(br * s)

    def stop(self) -> None:
        """Stop all four motors."""
        for m in self._motors:
            m.set_power(0)

    # ── Dead-reckoning linear moves ────────────────────────────────────────────

    def forward(self, distance_m: float, power: float = 50.0) -> None:
        """Move forward by *distance_m* metres."""
        self._strafe_move(abs(distance_m), abs(power), 0.0)

    def backward(self, distance_m: float, power: float = 50.0) -> None:
        """Move backward by *distance_m* metres."""
        self._strafe_move(abs(distance_m), -abs(power), 0.0)

    def strafe_left(self, distance_m: float, power: float = 50.0) -> None:
        """Strafe left by *distance_m* metres."""
        self._strafe_move(abs(distance_m), 0.0, -abs(power))

    def strafe_right(self, distance_m: float, power: float = 50.0) -> None:
        """Strafe right by *distance_m* metres."""
        self._strafe_move(abs(distance_m), 0.0, abs(power))

    def strafe(self, distance_m: float, angle_deg: float,
               power: float = 50.0) -> None:
        """Move in an arbitrary robot-relative direction.

        Parameters
        ----------
        distance_m:
            Distance to travel in metres.
        angle_deg:
            Direction relative to the robot's forward axis.
            ``0°`` = forward, ``90°`` = right, ``180°`` = backward, ``270°`` = left.
        power:
            Motor power magnitude (0–100).

        Example::

            drive.strafe(0.3, 45)   # move diagonally: forward-right
            drive.strafe(0.5, 270)  # strafe left (same as strafe_left)
        """
        a  = math.radians(angle_deg)
        vx = abs(power) * math.cos(a)
        vy = abs(power) * math.sin(a)   # positive = right
        self._strafe_move(abs(distance_m), vx, vy)

    def _strafe_move(self, dist_m: float, vx: float, vy: float) -> None:
        starts     = [enc.count for enc in self._encs]
        ramp_start = dist_m * (1.0 - _RAMP_FRAC)
        self.move(vx, vy)
        while True:
            ds = [(self._encs[i].count - starts[i]) * self._mpt
                  for i in range(4)]
            fl, fr, bl, br = ds
            dx       = (fl + fr + bl + br) * 0.25
            dy       = (-fl + fr + bl - br) * 0.25
            traveled = math.sqrt(dx * dx + dy * dy)
            if traveled >= dist_m - _DIST_TOL:
                break
            if traveled > ramp_start:
                frac  = max(0.0, (dist_m - traveled) / (dist_m * _RAMP_FRAC))
                scale = max(_MIN_PWR / 100.0, frac)
                self.move(vx * scale, vy * scale)
            time.sleep(0.02)
        self.stop()

    # ── Dead-reckoning rotation ────────────────────────────────────────────────

    def rotate(self, angle_deg: float, power: float = 40.0) -> None:
        """Rotate in place.  Positive = CCW (left).  Negative = CW (right)."""
        pwr  = abs(power)
        sign = 1.0 if angle_deg >= 0 else -1.0

        if self._imu and self._imu.connected:
            start = self._imu.heading
            self.move(0.0, 0.0, sign * pwr)
            while True:
                turned    = _hdiff(self._imu.heading, start)
                remaining = angle_deg - turned
                if abs(remaining) <= _ANG_TOL:
                    break
                if abs(remaining) < 20.0:
                    p = max(15.0, pwr * abs(remaining) / 20.0)
                    self.move(0.0, 0.0, sign * p)
                time.sleep(0.02)
        else:
            arc    = math.radians(abs(angle_deg)) * self._rk
            starts = [enc.count for enc in self._encs]
            self.move(0.0, 0.0, sign * pwr)
            while True:
                traveled = sum(
                    abs(self._encs[i].count - starts[i]) * self._mpt
                    for i in range(4)
                ) / 4.0
                if traveled >= arc - _DIST_TOL:
                    break
                time.sleep(0.02)

        self.stop()

    def turn_left(self, angle_deg: float, power: float = 40.0) -> None:
        """Turn left (counter-clockwise) by *angle_deg* degrees."""
        self.rotate(abs(angle_deg), power)

    def turn_right(self, angle_deg: float, power: float = 40.0) -> None:
        """Turn right (clockwise) by *angle_deg* degrees."""
        self.rotate(-abs(angle_deg), power)
