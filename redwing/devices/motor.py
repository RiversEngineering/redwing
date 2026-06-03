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

    def set_pid(self, kp: float, ki: float, kd: float):
        """Set PID gains for closed-loop velocity control.

        Only needed if the default tuning does not work well for your robot.
        """
        self._conn.send_command(cmd="set_pid", port=self._id, kp=kp, ki=ki, kd=kd)
