"""DC motor control."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .encoder import Encoder


class MotorGroup:
    """A set of motors that move together as a single drive side.

    All motors receive the same ``set_power()`` command simultaneously.
    Individual motors can still be :attr:`~Motor.inverted` to correct for
    back-to-back or mirrored mounting without rewiring.

    An optional *encoder* designates which physical encoder represents this
    group's position.  When a ``MotorGroup`` is passed to
    :meth:`~redwing.robot.Robot.differential_drive` or
    :meth:`~redwing.robot.Robot.mecanum_drive`, the drive system uses this
    encoder automatically — no need to specify it separately.

    Create via :meth:`~redwing.robot.Robot.motor_group`, not directly::

        lm1 = robot.motor(robot.D0)
        lm2 = robot.motor(robot.D2)
        lm2.inverted = True        # back motor faces the opposite direction

        le   = robot.encoder(robot.S0)
        left = robot.motor_group(lm1, lm2, encoder=le)

        drive = robot.differential_drive(
            left=left, right=right,
            wheel_diameter_mm=60,
            track_width_mm=150,
            ticks_per_rev=1440,
        )
    """

    def __init__(self, motors: list["Motor"],
                 encoder: "Encoder | None" = None) -> None:
        if not motors:
            raise ValueError("MotorGroup requires at least one motor.")
        self._motors  = motors
        self._encoder = encoder

    @property
    def encoder(self) -> "Encoder | None":
        """The designated encoder for this motor group, or ``None``."""
        return self._encoder

    @encoder.setter
    def encoder(self, enc: "Encoder | None") -> None:
        """Assign or re-assign the encoder after the group is created."""
        self._encoder = enc

    @property
    def motors(self) -> list["Motor"]:
        """The individual :class:`Motor` objects in this group (read-only list)."""
        return list(self._motors)

    # ── Motor-compatible interface ─────────────────────────────────────────────

    def set_power(self, value: float) -> None:
        """Set all motors to *value* percent (−100 to +100)."""
        for m in self._motors:
            m.set_power(value)

    def stop(self) -> None:
        """Stop all motors in the group."""
        for m in self._motors:
            m.stop()

    @property
    def power(self) -> float:
        """Power of the first motor in the group (proxy for the group's power)."""
        return self._motors[0].power

    def set_bias(self, power: float, peak_count: "int | None" = None,
                 ticks_per_rev: "float | None" = None) -> None:
        """Set the same bias on every motor in the group (see :meth:`Motor.set_bias`)."""
        for m in self._motors:
            m.set_bias(power, peak_count, ticks_per_rev)

    def set_min_power(self, value: float) -> None:
        """Set the drive-system minimum power on every motor in the group."""
        for m in self._motors:
            m.set_min_power(value)

    @property
    def min_power(self) -> "float | None":
        """Highest :attr:`Motor.min_power` in the group, or ``None`` if none set.

        The highest one is used so that every motor in the group still moves.
        """
        values = [m.min_power for m in self._motors if m.min_power is not None]
        return max(values) if values else None

    def __repr__(self) -> str:
        ids = [m._id for m in self._motors]
        enc = self._encoder._id if self._encoder else None
        return f"MotorGroup(motors={ids}, encoder={enc})"


class Motor:
    """Controls a brushed DC motor.

    Power is set as a percentage: -100 (full reverse) to +100 (full forward).
    This is the raw PWM duty cycle — distinct from *velocity*, which is the
    measured speed in ticks/s used for closed-loop control.

    Example::

        left = robot.D0.motor()
        left.set_power(75)    # 75% forward
        left.set_power(-50)   # 50% reverse
        left.stop()
    """

    def __init__(self, port_id: int, conn, motor_type: str, robot=None):
        self._id = port_id
        self._conn = conn
        self._type = motor_type
        self._power = 0.0
        self._encoder = None
        self._min_power = None
        self._inverted       = False
        self._code_invert_set = False  # True once student code sets motor.inverted
        self._ff_set = False           # True once set_feedforward() is called
        self._bias_set = False         # True once set_bias() turns a bias on
        self._robot = robot
        if robot is not None:
            robot._motors.append(self)

    def _check_started(self):
        if self._robot is not None and not self._robot._started:
            raise RuntimeError(
                "Call robot.start() before setting motor power or velocity."
            )

    # ------------------------------------------------------------------
    # Power (open-loop PWM percentage)
    # ------------------------------------------------------------------

    @property
    def power(self) -> float:
        """Current motor power as a percentage from -100 to +100.

        During open-loop control this reflects the last commanded value.
        During PID control (velocity or position) this reflects the actual
        output being driven by the firmware, updated at the state broadcast rate.
        """
        state = self._conn.get_port_state(self._id)
        if state and "value" in state:
            return state["value"] / 100.0
        return self._power

    def _effective_inverted(self) -> bool:
        """Return the active invert flag.  Code takes precedence over dashboard.

        The Pico applies the inversion itself (see :attr:`inverted`); this is
        only used to check that the firmware supports it.
        """
        if self._code_invert_set:
            return self._inverted
        return self._conn.get_all_state().get("port_invert", {}).get(str(self._id), False)

    def set_power(self, value: float):
        """Set motor power as a percentage from -100 (full reverse) to +100 (full forward).

        This sets the raw PWM duty cycle — not a closed-loop speed target.
        For speed control use :meth:`set_velocity` with an attached encoder.

        Example::

            motor.set_power(50)    # half power forward
            motor.set_power(-100)  # full reverse
        """
        self._check_started()
        value = max(-100.0, min(100.0, float(value)))
        self._power = value          # inversion is applied on the Pico
        self._conn.send_command(cmd="set_motor", port=self._id, value=int(value * 100))

    # ------------------------------------------------------------------
    # Direction
    # ------------------------------------------------------------------

    @property
    def inverted(self) -> bool:
        """Whether the motor direction is inverted."""
        return self._inverted

    @inverted.setter
    def inverted(self, value: bool):
        """Set to True to flip the motor direction without rewiring.

        The flag lives on the Pico, so it applies to everything the motor
        does: ``set_power()``, ``set_velocity()`` and ``go_to_position()``.
        It does not flip the encoder; for PID control the encoder count must
        still go up when this motor is given positive power (use
        ``encoder.invert()`` if it doesn't).
        """
        self._inverted        = bool(value)
        self._code_invert_set = True
        self._conn.send_command(cmd="set_motor_invert", port=self._id, inverted=self._inverted)

    def invert(self, inverted: bool = True):
        """Flip the motor direction without rewiring.

        Same as setting :attr:`inverted`.  Pass ``False`` to undo.

        Example::

            right.invert()         # right motor now spins the other way
            right.invert(False)    # back to normal
        """
        self.inverted = inverted

    def stop(self):
        """Stop this motor immediately (set power to 0)."""
        self.set_power(0)

    def set_min_power(self, value: float):
        """Set the lowest power (%) a drive system will give this motor.

        Used only by the blocking moves of
        :class:`~redwing.odometry.DifferentialDrive` and
        :class:`~redwing.odometry.MecanumDrive` (``forward()``, ``rotate_left()``,
        ``rotate_to()``, ...), which slow down near the end of a move.  Set it to
        roughly the smallest power that still makes the wheel turn, so the
        robot doesn't stall just short of its target.

        Does **not** affect ``set_power()``, ``drive.drive()`` /
        ``drive.move()``, or position PID (see ``output_floor`` and
        ``output_boost`` in :meth:`set_position_options` for that).

        Example::

            left.set_min_power(18)
        """
        value = float(value)
        if not 0.0 <= value <= 100.0:
            raise ValueError("min_power must be between 0 and 100.")
        self._min_power = value

    @property
    def min_power(self) -> "float | None":
        """Minimum drive-system power set by :meth:`set_min_power`, or ``None``."""
        return self._min_power

    # ------------------------------------------------------------------
    # Closed-loop velocity control
    # ------------------------------------------------------------------

    def attach_encoder(self, encoder):
        """Attach a quadrature encoder to enable closed-loop velocity control.

        Example::

            left_motor = robot.D0.motor()
            left_enc   = robot.D1.encoder()
            left_motor.attach_encoder(left_enc)
            left_motor.set_velocity(300)   # ticks per second
        """
        self._encoder = encoder
        self._conn.send_command(
            cmd="attach_encoder",
            motor_port=self._id,
            encoder_port=encoder._id,
        )

    @property
    def encoder(self) -> "Encoder | None":
        """The encoder attached with :meth:`attach_encoder`, or ``None``."""
        return self._encoder

    @property
    def velocity(self) -> float:
        """Target velocity in encoder ticks per second (closed-loop only)."""
        if self._encoder is None:
            raise RuntimeError(
                "No encoder attached to this motor. "
                "Call motor.attach_encoder(encoder) before using velocity control."
            )
        return self._conn.get_port_state(self._id).get("target_velocity", 0.0)

    def set_velocity(self, value: float):
        """Set target velocity in encoder ticks per second (closed-loop control)."""
        self._check_started()
        if self._encoder is None:
            raise RuntimeError(
                "No encoder attached to this motor. "
                "Call motor.attach_encoder(encoder) before using velocity control."
            )
        self._conn.send_command(cmd="set_velocity", port=self._id, velocity=float(value))

    @property
    def actual_velocity(self) -> float:
        """Measured velocity in encoder ticks per second."""
        if self._encoder is None:
            return 0.0
        return self._encoder.velocity

    def set_feedforward(self, kv: float, ks: float = 0.0):
        """Add feedforward to velocity control (:meth:`set_velocity` only).

        Feedforward is the power the target speed *should* need, worked out
        before measuring anything; PID then only corrects what's left.  That
        makes velocity control respond faster and need less integral.  Both
        default to 0, which is plain PID.  Position control
        (:meth:`go_to_position`) is not affected.

        Args:
            kv: % power per tick/s of target speed.  Estimate it as
                ``100 / top_speed``, where *top_speed* is the encoder velocity
                (ticks/s) at full power.
            ks: % power added in the direction of travel to overcome static
                friction, roughly the smallest power that makes the wheel turn.

        Example::

            # Wheel spins at about 2400 ticks/s at full power
            motor.set_feedforward(100 / 2400, ks=8)
            motor.set_pid(0.05, 0.02, 0)      # small gains: FF does most of the work
            motor.set_velocity(1200)
        """
        self._ff_set = True
        self._conn.send_command(cmd="set_vel_ff", port=self._id, kv=float(kv), ks=float(ks))

    def set_bias(self, power: float, peak_count: "int | None" = None,
                 ticks_per_rev: "float | None" = None):
        """Add a fixed extra power for a load that always pushes on the mechanism.

        Some mechanisms always need some power just to stay put: an arm or
        lift held up against gravity, a spring or rubber band pulling one way.
        The bias supplies that power, so the PID only corrects what's left.
        It's 0 (off) until you set it.

        It applies to :meth:`go_to_position`, :meth:`move_by` and
        :meth:`set_velocity`, including while the motor is holding still at its
        target, and is added on top of ``max_speed``.  It does **not** apply to
        :meth:`set_power` or :meth:`stop`, which set exactly the power you give.

        **Constant bias** (lifts, springs, tension): pass just *power*.

        **Cosine bias** (arms): the load is strongest when the arm sticks out
        level and fades to 0 as it points straight up or down.  Also pass
        *peak_count*, the encoder count where the arm is level, and
        *ticks_per_rev*, encoder ticks for one full turn of the arm (after any
        gearing).  The power then follows
        ``power × cos(angle away from peak_count)``, and flips sign once the
        arm passes straight up, just like gravity does.

        Args:
            power: % power at full strength.  Find it by hand: the power that
                just holds the mechanism still (the arm level, for an arm).
                Its sign is the direction that pushes against the load.
                0 turns the bias off.
            peak_count: Cosine only: encoder count where the bias is strongest.
            ticks_per_rev: Cosine only: encoder ticks per full turn of the
                mechanism.

        Example::

            lift.set_bias(12)                          # lift needs 12% to hold

            arm.encoder.reset()                        # arm resting straight down
            arm.set_bias(15, peak_count=360, ticks_per_rev=1440)   # level = 90° up
            arm.go_to_position(360)
        """
        power = float(power)
        if not -100.0 <= power <= 100.0:
            raise ValueError("bias power must be between -100 and 100.")
        if (peak_count is None) != (ticks_per_rev is None):
            raise ValueError("For a cosine bias pass both peak_count and ticks_per_rev; "
                             "for a constant bias pass neither.")
        if ticks_per_rev is not None and float(ticks_per_rev) <= 0:
            raise ValueError("ticks_per_rev must be greater than 0.")
        if power == 0.0:
            mode = "off"
        elif ticks_per_rev is None:
            mode = "constant"
        else:
            mode = "cosine"
        self._bias_set = self._bias_set or mode != "off"
        self._conn.send_command(
            cmd="set_bias", port=self._id, mode=mode, power=power,
            peak_count=int(peak_count or 0), ticks_per_rev=float(ticks_per_rev or 0.0),
        )

    def set_pid(self, kp: float, ki: float, kd: float, integral_max: float = None):
        """Set PID gains for closed-loop velocity or position control.

        Args:
            kp: Proportional gain.
            ki: Integral gain.
            kd: Derivative gain.
            integral_max: Optional cap on the integral accumulator. When set, the
                integral term can contribute at most ``ki * integral_max`` to the
                motor output, preventing runaway windup from long-held errors.
                Omit or pass ``None`` to leave uncapped (the default).

        Example::

            # Cap the integral so KI can contribute at most 3000 (30% power)
            # when ki=100: integral_max = 3000 / 100 = 30
            motor.set_pid(20, 100, 0.5, integral_max=30)
        """
        kw = {} if integral_max is None else {"integral_max": float(integral_max)}
        self._conn.send_command(cmd="set_pid", port=self._id, kp=kp, ki=ki, kd=kd, **kw)

    # ------------------------------------------------------------------
    # Closed-loop position control
    # ------------------------------------------------------------------

    def go_to_position(self, target: float, max_speed: float = None, keep_integral: bool = False):
        """Move to an absolute encoder position using PID control.

        The motor runs until the encoder count reaches *target* ticks.
        Use :attr:`Encoder.count` to check progress, or poll until the
        encoder count is close enough for your application.

        Calling this cancels any active velocity control on this motor.

        Args:
            target: Target encoder tick count (absolute).
            max_speed: Optional speed cap as a percentage (0–100). Defaults
                to full speed. Useful for approaching a position slowly.
            keep_integral: When False (the default), the PID integral
                accumulator is reset to zero before the move starts. This
                is correct for discrete commanded moves to a new position.
                Set to True when the target updates continuously (e.g. a
                joystick streaming small increments, a trajectory follower,
                or sensor-based position correction) so that the integral
                can compensate for steady loads such as gravity across
                successive target updates.

                **Warning**: when True, a stale integral from a previous
                direction can briefly oppose a reversal until anti-windup
                clears it.  Always set ``integral_max`` via
                :meth:`set_pid` when using this option.

        Example::

            arm_motor.go_to_position(500)                    # discrete move
            arm_motor.go_to_position(500, max_speed=30)      # cap at 30%
            arm_motor.go_to_position(joystick_target,        # streaming
                                     keep_integral=True)
        """
        self._check_started()
        if self._encoder is None:
            raise RuntimeError(
                "No encoder attached to this motor. "
                "Call motor.attach_encoder(encoder) before using position control."
            )
        speed_limit = 0
        if max_speed is not None:
            speed_limit = max(0, min(10000, int(float(max_speed) * 100)))
        self._conn.send_command(
            cmd="set_position",
            port=self._id,
            target=int(target),
            speed_limit=speed_limit,
            keep_integral=bool(keep_integral),
        )

    def set_position_options(self, deadband: float = 0, output_floor: float = 0,
                             ramp_rate: float = 0, d_alpha: float = 1.0,
                             approach_factor: float = 0, output_boost: float = 0):
        """Configure position PID options. All settings persist until changed.

        Args:
            deadband: Within ±deadband ticks of target, PID output is zeroed (a
                :meth:`set_bias` stays on) and integral is frozen. Prevents hunting on chain/belt drives with backlash.
                Default 0 (off).
            output_floor: Minimum motor output (%) when outside deadband. Ensures
                the motor overcomes static friction when the PID computes a small
                output. Default 0 (off).
            ramp_rate: Max rate (ticks/s) at which the internal setpoint moves toward
                the commanded target. Limits the initial impulse that excites
                resonance without requiring ``max_speed``. Default 0 (instant).
            d_alpha: EMA alpha for the derivative low-pass filter (0 < alpha ≤ 1.0).
                Lower values filter more aggressively. 1.0 = no filter (default).
                Values around 0.1–0.3 attenuate chain/belt chatter without
                significantly lagging the damping response.
            approach_factor: Deceleration factor for the setpoint ramp (0 < factor ≤ 1.0).
                The ramp step is capped to ``|remaining| × factor`` so the setpoint
                slows proportionally as it nears the final target — fast on the bulk
                of the move, automatic deceleration in the approach zone. Default 0 (off).
                With ramp_rate=300, factor=0.1 starts decelerating ~30 ticks before
                the ramp setpoint reaches the target. Lower values decelerate earlier
                and more gradually; try 0.05–0.15.
            output_boost: Dead-zone compensation (%). Any nonzero PID output is
                pushed away from zero by this amount, and the rest of the range is
                scaled so ``max_speed`` is still the maximum (e.g. boost=8: a PID
                output of 2% becomes ~9.8%, 100% stays 100%). Set it to roughly
                the smallest power that makes the mechanism start moving. Helps
                geared/chain arms that settle in slow "steps" while the integral
                builds up. Unlike ``output_floor``, small outputs stay
                proportional, so it doesn't over-push while holding. Default 0 (off).

        Example::

            # Shoulder with plastic chain: fast bulk move, automatic deceleration
            # on approach, derivative noise filter, deadband for final settling.
            shoulder.set_position_options(
                ramp_rate=300,
                approach_factor=0.1,
                d_alpha=0.15,
                deadband=5,
                output_floor=7,
            )
        """
        self._conn.send_command(
            cmd="set_pos_options",
            port=self._id,
            deadband=float(deadband),
            output_floor=float(output_floor),
            ramp_rate=float(ramp_rate),
            d_alpha=float(d_alpha),
            approach_factor=float(approach_factor),
            output_boost=float(output_boost),
        )

    def move_by(self, delta: float, max_speed: float = None, keep_integral: bool = False):
        """Move by a relative number of encoder ticks from the current position.

        Reads the current encoder count and calls :meth:`go_to_position` with
        ``current + delta`` as the absolute target. Behaves like a stepper motor
        command: positive *delta* moves forward, negative moves backward.

        Calling this cancels any active velocity control on this motor.

        Args:
            delta: Number of encoder ticks to move relative to the current position.
            max_speed: Optional speed cap as a percentage (0–100). Defaults to full speed.
            keep_integral: Passed through to :meth:`go_to_position`. See that
                method for full documentation.

        Example::

            arm_motor.move_by(200)              # move 200 ticks forward
            arm_motor.move_by(-100, max_speed=40)  # move 100 ticks back at 40% speed
        """
        self._check_started()
        if self._encoder is None:
            raise RuntimeError(
                "No encoder attached to this motor. "
                "Call motor.attach_encoder(encoder) before using position control."
            )
        current = self._encoder.count
        self.go_to_position(current + delta, max_speed, keep_integral)
