"""DC motor control."""


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
        self._inverted = False
        self._robot = robot

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
        """Last commanded power as a percentage from -100 to +100."""
        return self._power

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
        if self._inverted:
            value = -value
        self._power = value
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
        """Set to True to flip the motor direction without rewiring."""
        self._inverted = bool(value)

    def stop(self):
        """Stop this motor immediately (set power to 0)."""
        self.set_power(0)

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
