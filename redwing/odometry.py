"""Dead-reckoning odometry and drive control.

Provides :class:`DifferentialDrive` and :class:`MecanumDrive` — objects that
track a 2-D robot pose using encoder counts fused with an optional IMU heading,
and expose blocking movement commands for dead-reckoning navigation.

Quick start — differential drive::

    robot = redwing.Robot()

    lm = robot.motor(robot.D0)
    rm = robot.motor(robot.D1)
    rm.invert()                 # flip right motor if it spins backwards

    lm.attach_encoder(robot.encoder(robot.D2))
    rm.attach_encoder(robot.encoder(robot.D3))
    imu = robot.imu()           # optional but strongly recommended

    drive = robot.differential_drive(
        left_motor=lm, right_motor=rm,    # attached encoders used automatically
        imu=imu,
        wheel_diameter_mm=60,
        track_width_mm=410,
        ticks_per_rev=1440,
    )
    robot.start()

    drive.forward(0.5)      # 0.5 m forward
    drive.rotate_right(90)  # 90° clockwise
    print(drive.pose)       # (x_m, y_m, heading_deg)

Quick start — mecanum drive::

    drive = robot.mecanum_drive(
        fl=fl_motor, fr=fr_motor,     # each with an attached encoder
        bl=bl_motor, br=br_motor,
        wheel_diameter_mm=100,
        track_width_mm=410,
        wheelbase_mm=280,
        ticks_per_rev=1440,
    )
    robot.start()

    drive.forward(0.5)
    drive.strafe_right(0.3)
    drive.rotate_by(-90)    # 90° clockwise (right)
    drive.strafe(0.4, 45)   # move diagonally at 45° (forward-left)

Coordinate frame
----------------
The robot uses a right-hand coordinate system:

- ``+X``: forward (the direction the robot faces at startup)
- ``+Y``: left
- ``+Z``: up
- ``heading``: rotation around +Z, degrees, 0 at startup.
  **Positive = counter-clockwise** (left turn), consistent with
  ``imu.heading``.  Use ``rotate_left()`` / ``rotate_right()`` to avoid
  thinking about sign conventions.

Every signed drive value follows this frame (ROS REP 103): positive
``move_by`` / ``vx`` = forward, positive ``strafe_by`` / ``vy`` = **left**,
positive ``rotate_by`` / ``omega`` / ``turn`` = counter-clockwise (left),
and ``strafe()`` angles are measured counter-clockwise from forward.

The ``imu.acceleration`` vector and ``imu.quaternion`` are expressed in the
same robot frame once :meth:`~redwing.devices.imu.IMU.set_mount_rotation`
has been called.

Heading note
~~~~~~~~~~~~
The IMU heading (0–360°, increasing = CCW from above) matches the mathematical
convention.  If your robot turns the wrong direction for a given command,
call ``motor.invert()`` on the relevant motor(s).
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
_MIN_PWR   = 20.0        # default minimum power during straight-move ramp-down
_MIN_TURN_PWR = 15.0     # default minimum power while turning
_SLOW_DEG  = 20.0        # turns slow down within this many degrees of the target
_DIST_TOL  = 0.01        # 1 cm positional tolerance
_ANG_TOL   = 1.5         # 1.5° angular tolerance

# ── Angle helpers ───────────────────────────────────────────────────────────────

def _wrap(deg: float) -> float:
    """Wrap angle to (−180, 180]."""
    return (deg + 180.0) % 360.0 - 180.0


def _hdiff(new_deg: float, old_deg: float) -> float:
    """Signed shortest-arc difference (new − old), clamped to (−180, 180]."""
    return _wrap(new_deg - old_deg)


def _turn_angle(current_deg: float, target_deg: float, direction: str) -> float:
    """Signed rotation (CCW positive) from *current_deg* to *target_deg*.

    *direction* is ``"shortest"``, ``"left"`` (CCW) or ``"right"`` (CW).
    """
    d = str(direction).lower()
    if d == "shortest":
        return _hdiff(target_deg, current_deg)
    if d == "left":
        return (target_deg - current_deg) % 360.0
    if d == "right":
        return -((current_deg - target_deg) % 360.0)
    raise ValueError("direction must be 'shortest', 'left', or 'right'.")


def _floor(motor, default: float | None) -> float | None:
    """The motor's own min_power if it set one, otherwise *default*."""
    mp = getattr(motor, "min_power", None)
    return default if mp is None else mp


def _floored(power: float, motor, default: float | None) -> float:
    """Power magnitude raised to the motor's floor, capped at 100."""
    f = _floor(motor, default)
    if f is not None:
        power = max(power, f)
    return min(power, 100.0)


# ── Velocity control (shared by both drives) ───────────────────────────────────

_VEL_MODES = ("python", "pico")
_VEL_KP = 1.0    # default feedback: % per m/s of error, as a multiple of feedforward kv
_VEL_KI = 2.0    # default integral: per second, as a multiple of kp
_VEL_I_MAX = 20.0  # most power (%) the integral may add


def _motors_of(m) -> list:
    """The individual motors behind a drive wheel (a Motor or a MotorGroup)."""
    return list(getattr(m, "motors", [m]))


class _VelocityControl:
    """Closed-loop wheel speed for the drives.

    A drive provides ``_mpt`` (metres per tick) and ``_vel_wheels()`` →
    ``[(motor_or_group, encoder, encoder_sign), ...]``, and turns a robot
    speed into wheel speeds in its own ``set_velocity()``.

    Each wheel gets feedforward (``kv * target + ks * sign(target)``) plus
    PI feedback on the measured encoder speed.  ``kv`` comes from
    :meth:`set_max_speed` / :meth:`set_max_rpm`; ``ks`` is each motor's ``min_power`` (0 if unset).
    The loop runs either in the drive's 50 Hz Python thread (``"python"``,
    default) or on the Pico at 100 Hz (``"pico"``).
    """

    def _vel_init(self):
        self._max_speed   = None     # m/s at 100 % power
        self._vel_mode    = "python"
        self._vel_kp_user = None     # % per m/s; None = default from max speed
        self._vel_ki_user = None
        self._vel_targets = None     # per-wheel m/s while Python-mode control is on
        self._vel_integ   = []
        self._pico_ready  = False

    # ── Settings ──────────────────────────────────────────────────────────────

    def set_max_speed(self, speed_mps: float) -> None:
        """Set the wheel speed (m/s) the robot reaches at full power.

        Needed before :meth:`set_velocity`: it is the feedforward that does
        most of the work.  Measure it by driving at ``power=100`` and reading
        the encoder speed, or start with an estimate and adjust until
        ``set_velocity()`` lands close to the asked-for speed.
        """
        if speed_mps <= 0:
            raise ValueError("max speed must be positive (m/s at full power).")
        self._max_speed  = float(speed_mps)
        self._pico_ready = False

    def set_max_rpm(self, rpm: float, gear_ratio: float = 1.0) -> None:
        """Set top speed from the motor's rated RPM (the number on the motor).

        Same as :meth:`set_max_speed`, worked out from the wheel diameter:
        ``rpm / gear_ratio / 60 × π × wheel diameter``.

        The rated RPM is with no load, so the robot's real top speed is
        usually 10–25 % lower.  That's fine for most driving; if the robot
        can't keep up near full stick, measure the real speed and use
        :meth:`set_max_speed` instead.

        Args:
            rpm: Motor output RPM at full power, as printed on the motor.
            gear_ratio: Motor turns per wheel turn, for chains or gears
                between the motor and the wheel.  2 means the wheel turns at
                half the motor's speed.  Default 1 (wheel on the motor shaft).

        Example::

            drive.set_max_rpm(312)                  # wheel straight on the motor
            drive.set_max_rpm(435, gear_ratio=2)    # 2:1 chain reduction
        """
        if rpm <= 0:
            raise ValueError("rpm must be positive.")
        if gear_ratio <= 0:
            raise ValueError("gear_ratio must be positive (motor turns per wheel turn).")
        self.set_max_speed(float(rpm) / float(gear_ratio) / 60.0 * self._wheel_circ)

    @property
    def max_speed(self) -> "float | None":
        """Top speed in m/s, from :meth:`set_max_speed` or :meth:`set_max_rpm`.

        ``None`` until one of those is called.  The fastest the robot can drive
        straight; :meth:`set_velocity` scales faster requests down to it.
        """
        return self._max_speed

    @property
    def max_angular_speed(self) -> "float | None":
        """Top rotation speed in degrees/s when rotating in place.

        Worked out from :attr:`max_speed` and the drive's size.  ``None`` until
        the top speed is set.  Moving and rotating at once shares the wheels'
        speed, so each gets less.
        """
        if self._max_speed is None:
            return None
        return math.degrees(self._max_speed / self._spin_r)

    def set_velocity_mode(self, mode: str) -> None:
        """Choose where velocity control runs: ``"python"`` (default) or ``"pico"``.

        ``"python"`` runs in the drive's own 50 Hz loop and works with any
        firmware.  ``"pico"`` runs on the Pico at 100 Hz: it reacts faster and
        isn't slowed down by busy student code, but needs Pico firmware v1+.
        Student code is the same either way.
        """
        m = str(mode).lower()
        if m not in _VEL_MODES:
            raise ValueError("velocity mode must be 'python' or 'pico'.")
        if m != self._vel_mode:
            self.stop()
        self._vel_mode   = m
        self._pico_ready = False

    def set_velocity_gains(self, kp: float | None = None, ki: float | None = None) -> None:
        """Override the feedback gains (% power per m/s of speed error).

        Defaults: ``kp`` equals the feedforward gain (``100 / max_speed``),
        ``ki`` is twice ``kp``.  Lower ``kp`` if the speed oscillates; raise
        it if the robot is slow to recover when a wheel is loaded.
        """
        self._vel_kp_user = None if kp is None else float(kp)
        self._vel_ki_user = None if ki is None else float(ki)
        self._pico_ready  = False

    def _vel_gains(self) -> tuple[float, float, float]:
        if self._max_speed is None:
            raise RuntimeError(
                "Call drive.set_max_rpm(rpm) or drive.set_max_speed(m_per_s) before "
                "drive.set_velocity(): the drive needs the robot's top speed at full power."
            )
        kv = 100.0 / self._max_speed
        kp = kv * _VEL_KP if self._vel_kp_user is None else self._vel_kp_user
        ki = kp * _VEL_KI if self._vel_ki_user is None else self._vel_ki_user
        return kv, kp, ki

    # ── Commands ──────────────────────────────────────────────────────────────

    def _vel_command(self, wheel_mps: list[float]) -> None:
        """Run each wheel at the given speed (m/s), scaled down together if
        any would exceed max speed (keeps the direction of travel)."""
        kv, kp, ki = self._vel_gains()
        peak = max(abs(v) for v in wheel_mps)
        if peak > self._max_speed:
            wheel_mps = [v * self._max_speed / peak for v in wheel_mps]

        if self._vel_mode == "pico":
            self._vel_targets = None
            if not self._pico_ready:
                self._vel_setup_pico(kv, kp, ki)
            for (m, _enc, sign), v in zip(self._vel_wheels(), wheel_mps):
                for motor in _motors_of(m):
                    motor.set_velocity(sign * v / self._mpt)
            return

        if self._vel_targets is None:
            self._vel_integ = [0.0] * len(wheel_mps)
        self._vel_targets = list(wheel_mps)

    def _vel_setup_pico(self, kv: float, kp: float, ki: float) -> None:
        """Give every wheel motor its encoder, feedforward and PID on the Pico.

        Gains are converted from m/s to the Pico's ticks/s.
        """
        if self._robot is not None:
            state = self._robot._conn.get_all_state()
            version = state.get("firmware_version", 0)
            if version is not None and version < 1:
                raise RuntimeError(
                    "Pico velocity mode needs newer Pico firmware. Flash it from "
                    "the dashboard's Firmware tab, or use set_velocity_mode(\"python\").")
        mpt = self._mpt
        for m, enc, sign in self._vel_wheels():
            if sign < 0:
                raise RuntimeError(
                    "Pico velocity mode can't use the drive's invert_* encoder "
                    "flags. Use encoder.invert() instead.")
            for motor in _motors_of(m):
                if not hasattr(motor, "set_velocity"):
                    raise RuntimeError("Pico velocity mode needs D-port motors with encoders.")
                if motor.encoder is not enc:
                    motor.attach_encoder(enc)       # a group shares one encoder
                motor.set_feedforward(kv * mpt, _floor(motor, 0.0))
                i_max = _VEL_I_MAX / (ki * mpt) if ki > 0 else None
                motor.set_pid(kp * mpt, ki * mpt, 0.0, integral_max=i_max)
        self._pico_ready = True

    def _vel_off(self) -> None:
        """Leave Python-mode velocity control (any other drive command does this;
        on the Pico, the next set_power() ends velocity PID by itself)."""
        self._vel_targets = None

    def _vel_step(self) -> None:
        """One Python-mode control step; called from the drive's 50 Hz loop."""
        targets = self._vel_targets
        if targets is None:
            return
        kv, kp, ki = self._vel_gains()
        for i, ((m, enc, sign), target) in enumerate(zip(self._vel_wheels(), targets)):
            measured = sign * enc.velocity * self._mpt
            error    = target - measured
            if target == 0.0:
                self._vel_integ[i] = 0.0
            elif ki > 0:
                lim = _VEL_I_MAX / ki
                self._vel_integ[i] = max(-lim, min(lim, self._vel_integ[i] + error * _ODOM_DT))
            power = kv * target + kp * error + ki * self._vel_integ[i]
            if target != 0.0:
                ks = _floor(m, 0.0)
                power += ks if target > 0 else -ks
            elif abs(measured) < 0.02:
                power = 0.0                         # stopped: don't hum or creep
            if self._vel_targets is not targets:
                return                              # cancelled mid-step
            m.set_power(max(-100.0, min(100.0, power)))


# ── DifferentialDrive ───────────────────────────────────────────────────────────

class DifferentialDrive(_VelocityControl):
    """Two-wheel differential drive with odometry and dead-reckoning movement.

    Parameters
    ----------
    left_motor, right_motor:
        :class:`~redwing.devices.motor.Motor` objects (created with
        ``robot.motor()``).  If a motor spins backwards,
        call ``motor.invert()`` rather than using the ``invert_*`` flags.
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
        self._wheel_circ = math.pi * wheel_diameter_mm / 1000.0
        self._track = track_width_mm / 1000.0
        self._spin_r = self._track * 0.5   # wheel travel (m) per radian of rotation
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
        self._vel_init()

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
            self._vel_step()
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
            # dr - dl > 0 when right wheel moves more → CCW → positive dhdg.
            dhdg = math.degrees((dr - dl) / self._track)  # CCW positive

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
        self._vel_off()
        l = max(-100.0, min(100.0, forward - turn))
        r = max(-100.0, min(100.0, forward + turn))
        self._lm.set_power(l)
        self._rm.set_power(r)

    def set_velocity(self, vx: float, omega: float = 0.0) -> None:
        """Drive at a measured speed (non-blocking), using the encoders.

        Unlike :meth:`drive`, which sets power, this holds the asked-for speed
        whatever the load or battery level, so small joystick inputs give
        slow, steady motion.  Call :meth:`set_max_rpm` (or :meth:`set_max_speed`) once first.

        Parameters
        ----------
        vx:
            Forward speed in m/s (negative = backward).
        omega:
            Rotation in degrees per second.  Positive = **left (CCW)**.

        Runs until another drive command; :meth:`stop` ends it.  See
        :meth:`set_velocity_mode` for running it on the Pico instead.
        """
        w = math.radians(omega) * self._track * 0.5
        self._vel_command([vx - w, vx + w])

    def _vel_wheels(self):
        return [(self._lm, self._le, -1.0 if self._il else 1.0),
                (self._rm, self._re, -1.0 if self._ir else 1.0)]

    def stop(self) -> None:
        """Stop both drive motors immediately (also ends :meth:`set_velocity`)."""
        self._vel_off()
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

    def move_by(self, distance_m: float, power: float = 50.0) -> None:
        """Move straight by *distance_m* metres, then stop.

        Positive = **forward**, negative = **backward**.
        """
        if distance_m == 0:
            return
        self._linear_move(abs(distance_m), abs(power) if distance_m > 0 else -abs(power))

    def _push(self, sign: float, power: float) -> None:
        """Drive both sides straight, each at or above its minimum power."""
        self._vel_off()
        self._lm.set_power(sign * _floored(power, self._lm, _MIN_PWR))
        self._rm.set_power(sign * _floored(power, self._rm, _MIN_PWR))

    def _spin(self, sign: float, power: float) -> None:
        """Spin in place (sign +1 = CCW), each side at or above its minimum."""
        self._vel_off()
        self._lm.set_power(-sign * _floored(power, self._lm, _MIN_TURN_PWR))
        self._rm.set_power( sign * _floored(power, self._rm, _MIN_TURN_PWR))

    def _linear_move(self, dist_m: float, power: float) -> None:
        start_l  = self._le.count
        start_r  = self._re.count
        ramp_start = dist_m * (1.0 - _RAMP_FRAC)
        sign = 1.0 if power >= 0 else -1.0
        self._push(sign, abs(power))
        while True:
            dl       = abs(self._le.count - start_l) * self._mpt
            dr       = abs(self._re.count - start_r) * self._mpt
            traveled = (dl + dr) * 0.5
            if traveled >= dist_m - _DIST_TOL:
                break
            if traveled > ramp_start:
                frac = max(0.0, (dist_m - traveled) / (dist_m * _RAMP_FRAC))
                self._push(sign, abs(power) * frac)
            time.sleep(0.02)
        self.stop()

    # ── Dead-reckoning rotation ────────────────────────────────────────────────

    def rotate_by(self, angle_deg: float, power: float = 40.0) -> None:
        """Rotate in place by *angle_deg* degrees.

        Positive angle = **counter-clockwise** (left turn).
        Negative angle = **clockwise** (right turn).
        """
        if abs(angle_deg) <= _ANG_TOL:
            return
        pwr  = abs(power)
        sign = 1.0 if angle_deg >= 0 else -1.0   # +1 = CCW

        if self._imu and self._imu.connected:
            last   = self._imu.heading
            turned = 0.0
            self._spin(sign, pwr)
            while True:
                now     = self._imu.heading
                turned += _hdiff(now, last)        # CCW positive, unwrapped
                last    = now
                remaining = angle_deg - turned      # same sign as angle_deg until passed
                # Stop inside tolerance, or once past the target (never spin around again).
                if abs(remaining) <= _ANG_TOL or remaining * sign < 0:
                    break
                if abs(remaining) < _SLOW_DEG:
                    self._spin(sign, pwr * abs(remaining) / _SLOW_DEG)
                time.sleep(0.02)
        else:
            arc      = math.radians(abs(angle_deg)) * self._track * 0.5
            start_l  = self._le.count
            start_r  = self._re.count
            # CCW: right forward, left backward.  CW: the reverse.
            self._spin(sign, pwr)
            while True:
                dl       = abs(self._le.count - start_l) * self._mpt
                dr       = abs(self._re.count - start_r) * self._mpt
                traveled = (dl + dr) * 0.5
                if traveled >= arc - _DIST_TOL:
                    break
                time.sleep(0.02)

        self.stop()

    def rotate_left(self, angle_deg: float, power: float = 40.0) -> None:
        """Rotate left (counter-clockwise) in place by *angle_deg* degrees."""
        self.rotate_by(abs(angle_deg), power)

    def rotate_right(self, angle_deg: float, power: float = 40.0) -> None:
        """Rotate right (clockwise) in place by *angle_deg* degrees."""
        self.rotate_by(-abs(angle_deg), power)

    def rotate_to(self, heading_deg: float, direction: str = "shortest",
                power: float = 40.0) -> None:
        """Rotate in place to face an absolute *heading_deg* (same frame as :attr:`heading`).

        Because the target is absolute, any overshoot from one rotation is
        corrected by the next instead of adding up.

        Parameters
        ----------
        heading_deg:
            Heading to face, in degrees (0 = startup, positive = CCW).
        direction:
            ``"shortest"`` (default) takes the shorter way round,
            ``"left"`` always rotates counter-clockwise, ``"right"`` always
            rotates clockwise.

        Example::

            drive.rotate_to(90)                    # face 90°, shorter way
            drive.rotate_to(0, direction="left")   # back to 0°, rotating left
        """
        self.rotate_by(_turn_angle(self.heading, heading_deg, direction), power)

    # ── Old names, kept so existing programs still run ─────────────────────────
    rotate     = rotate_by
    turn_by    = rotate_by
    turn_left  = rotate_left
    turn_right = rotate_right
    turn_to    = rotate_to

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

    def strafe_by(self, *_a, **_kw):
        raise NotImplementedError(
            "Differential drive cannot strafe. Use MecanumDrive for sideways movement."
        )


# ── MecanumDrive ────────────────────────────────────────────────────────────────

class MecanumDrive(_VelocityControl):
    """Four-wheel mecanum (holonomic) drive with odometry and dead-reckoning.

    Wheel positions and standard roller orientation::

        FL (/45°)    FR (\\45°)
        BL (\\45°)   BR (/45°)

    Motor mixing (vx = forward, vy = left, ω = CCW rotation — all as %)::

        FL = vx − vy − ω
        FR = vx + vy + ω
        BL = vx + vy − ω
        BR = vx − vy + ω

    where ``vy > 0`` strafes **left** and ``ω > 0`` rotates **counter-clockwise**.

    Parameters
    ----------
    fl, fr, bl, br:
        Each is a ``(Motor, Encoder)`` tuple for that corner, e.g.::

            fl=(robot.motor(robot.D0), robot.encoder(robot.D4))

        (:meth:`Robot.mecanum_drive` also accepts a Motor with an attached
        encoder or a MotorGroup, and converts it to this form.)

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
        # Wheel travel per radian of rotation = (track + wheelbase) / 2
        self._rk      = (self._track + self._wb) * 0.5
        self._spin_r  = self._rk           # used by max_angular_speed
        self._wheel_circ = math.pi * wheel_diameter_mm / 1000.0
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
        self._vel_init()

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
            self._vel_step()
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
        # Robot-frame displacement (x = forward, y = left)
        dx_r = (fl + fr + bl + br) * 0.25
        dy_r = (-fl + fr + bl - br) * 0.25

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
            # Rotate robot-frame displacement into the world frame
            self._x += dx_r * cos_h - dy_r * sin_h
            self._y += dx_r * sin_h + dy_r * cos_h
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
            Strafe power.  Positive = **left**, negative = right.
        omega:
            Rotation power.  Positive = **counter-clockwise** (left), negative = CW.
        """
        self._vel_off()
        for m, p in zip(self._motors, self._mix(vx, vy, omega)):
            m.set_power(p)

    def set_velocity(self, vx: float, vy: float = 0.0, omega: float = 0.0) -> None:
        """Drive at a measured speed (non-blocking), using the encoders.

        Like :meth:`move`, but in real units and held at that speed whatever
        the load.  Call :meth:`set_max_rpm` (or :meth:`set_max_speed`) once first.

        Parameters
        ----------
        vx:
            Forward speed in m/s.
        vy:
            Sideways speed in m/s.  Positive = **left**.
        omega:
            Rotation in degrees per second.  Positive = **left (CCW)**.
        """
        # Wheel surface speed for rotation is omega × (half track + half wheelbase)
        k = math.radians(omega) * self._rk
        self._vel_command([vx - vy - k, vx + vy + k, vx + vy - k, vx - vy + k])

    def _vel_wheels(self):
        return [(m, e, -1.0 if inv else 1.0)
                for m, e, inv in zip(self._motors, self._encs, self._inverts)]

    @staticmethod
    def _mix(vx: float, vy: float, omega: float) -> list[float]:
        """Wheel powers (FL, FR, BL, BR), scaled down so none exceeds 100."""
        w  = [vx - vy - omega, vx + vy + omega, vx + vy - omega, vx - vy + omega]
        mx = max(max(abs(p) for p in w), 100.0)
        return [p * 100.0 / mx for p in w]

    def _move_floored(self, vx: float, vy: float, omega: float,
                      default: float | None) -> None:
        """Like :meth:`move`, but scale all four wheels up together until each
        main wheel reaches its minimum power.  Scaling them together keeps the
        direction of travel.  Wheels under half the fastest one (e.g. the
        idle pair on a diagonal) are ignored."""
        self._vel_off()
        w    = self._mix(vx, vy, omega)
        peak = max(abs(p) for p in w)
        s    = 1.0
        if peak > 0:
            for m, p in zip(self._motors, w):
                f = _floor(m, default)
                if f is not None and abs(p) >= 0.5 * peak:
                    s = max(s, f / abs(p))
            s = min(s, 100.0 / peak)
        for m, p in zip(self._motors, w):
            m.set_power(p * s)

    def stop(self) -> None:
        """Stop all four motors (also ends :meth:`set_velocity`)."""
        self._vel_off()
        for m in self._motors:
            m.set_power(0)

    # ── Dead-reckoning linear moves ────────────────────────────────────────────

    def forward(self, distance_m: float, power: float = 50.0) -> None:
        """Move forward by *distance_m* metres."""
        self._strafe_move(abs(distance_m), abs(power), 0.0)

    def backward(self, distance_m: float, power: float = 50.0) -> None:
        """Move backward by *distance_m* metres."""
        self._strafe_move(abs(distance_m), -abs(power), 0.0)

    def move_by(self, distance_m: float, power: float = 50.0) -> None:
        """Move straight by *distance_m* metres.  Positive = forward, negative = backward."""
        if distance_m == 0:
            return
        self._strafe_move(abs(distance_m), abs(power) if distance_m > 0 else -abs(power), 0.0)

    def strafe_left(self, distance_m: float, power: float = 50.0) -> None:
        """Strafe left by *distance_m* metres."""
        self._strafe_move(abs(distance_m), 0.0, abs(power))

    def strafe_right(self, distance_m: float, power: float = 50.0) -> None:
        """Strafe right by *distance_m* metres."""
        self._strafe_move(abs(distance_m), 0.0, -abs(power))

    def strafe_by(self, distance_m: float, power: float = 50.0) -> None:
        """Strafe sideways by *distance_m* metres.  Positive = **left**, negative = right
        (same as ``vy`` in :meth:`move`)."""
        if distance_m == 0:
            return
        self._strafe_move(abs(distance_m), 0.0, abs(power) if distance_m > 0 else -abs(power))

    def strafe(self, distance_m: float, angle_deg: float,
               power: float = 50.0) -> None:
        """Move in an arbitrary robot-relative direction.

        Parameters
        ----------
        distance_m:
            Distance to travel in metres.
        angle_deg:
            Direction relative to the robot's forward axis.
            Counter-clockwise from forward, like heading:
            ``0°`` = forward, ``90°`` = left, ``180°`` = backward, ``270°`` = right.
        power:
            Motor power magnitude (0–100).

        Example::

            drive.strafe(0.3, 45)   # move diagonally: forward-left
            drive.strafe(0.5, 270)  # strafe right (same as strafe_right)
        """
        a  = math.radians(angle_deg)
        vx = abs(power) * math.cos(a)
        vy = abs(power) * math.sin(a)   # positive = left
        self._strafe_move(abs(distance_m), vx, vy)

    def _strafe_move(self, dist_m: float, vx: float, vy: float) -> None:
        starts     = [enc.count for enc in self._encs]
        ramp_start = dist_m * (1.0 - _RAMP_FRAC)
        self._move_floored(vx, vy, 0.0, None)
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
                self._move_floored(vx * scale, vy * scale, 0.0, None)
            time.sleep(0.02)
        self.stop()

    # ── Dead-reckoning rotation ────────────────────────────────────────────────

    def rotate_by(self, angle_deg: float, power: float = 40.0) -> None:
        """Rotate in place by *angle_deg* degrees.  Positive = CCW (left).  Negative = CW (right)."""
        if abs(angle_deg) <= _ANG_TOL:
            return
        pwr  = abs(power)
        sign = 1.0 if angle_deg >= 0 else -1.0

        if self._imu and self._imu.connected:
            last   = self._imu.heading
            turned = 0.0
            self._move_floored(0.0, 0.0, sign * pwr, _MIN_TURN_PWR)
            while True:
                now     = self._imu.heading
                turned += _hdiff(now, last)        # CCW positive, unwrapped
                last    = now
                remaining = angle_deg - turned
                # Stop inside tolerance, or once past the target (never spin around again).
                if abs(remaining) <= _ANG_TOL or remaining * sign < 0:
                    break
                if abs(remaining) < _SLOW_DEG:
                    p = pwr * abs(remaining) / _SLOW_DEG
                    self._move_floored(0.0, 0.0, sign * p, _MIN_TURN_PWR)
                time.sleep(0.02)
        else:
            arc    = math.radians(abs(angle_deg)) * self._rk
            starts = [enc.count for enc in self._encs]
            self._move_floored(0.0, 0.0, sign * pwr, _MIN_TURN_PWR)
            while True:
                traveled = sum(
                    abs(self._encs[i].count - starts[i]) * self._mpt
                    for i in range(4)
                ) / 4.0
                if traveled >= arc - _DIST_TOL:
                    break
                time.sleep(0.02)

        self.stop()

    def rotate_left(self, angle_deg: float, power: float = 40.0) -> None:
        """Rotate left (counter-clockwise) in place by *angle_deg* degrees."""
        self.rotate_by(abs(angle_deg), power)

    def rotate_right(self, angle_deg: float, power: float = 40.0) -> None:
        """Rotate right (clockwise) in place by *angle_deg* degrees."""
        self.rotate_by(-abs(angle_deg), power)

    def rotate_to(self, heading_deg: float, direction: str = "shortest",
                power: float = 40.0) -> None:
        """Rotate in place to face an absolute *heading_deg*.

        Same as :meth:`DifferentialDrive.rotate_to`; *direction* is
        ``"shortest"`` (default), ``"left"``, or ``"right"``.
        """
        self.rotate_by(_turn_angle(self.heading, heading_deg, direction), power)

    # ── Old names, kept so existing programs still run ─────────────────────────
    rotate     = rotate_by
    turn_by    = rotate_by
    turn_left  = rotate_left
    turn_right = rotate_right
    turn_to    = rotate_to
