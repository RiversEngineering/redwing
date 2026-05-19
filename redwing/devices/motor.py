"""DC motor control."""


class Motor:
    """Controls a brushed DC motor.

    Speed is set as a percentage: -100 (full reverse) to 100 (full forward).

    Example::

        left = robot.D0.motor()
        left.set_speed(75)   # 75% forward
        left.set_speed(-50)  # 50% reverse
        left.stop()
    """

    def __init__(self, port_id: int, conn, motor_type: str, robot=None):
        self._id = port_id
        self._conn = conn
        self._type = motor_type
        self._speed = 0.0
        self._encoder = None
        self._inverted = False
        self._robot = robot

    def _check_started(self):
        if self._robot is not None and not self._robot._started:
            raise RuntimeError(
                "Call robot.start() before setting motor speed or velocity."
            )

    @property
    def speed(self) -> float:
        """Last commanded speed as a percentage from -100 to 100."""
        return self._speed

    def set_speed(self, value: float):
        """Set motor speed as a percentage from -100 (full reverse) to 100 (full forward)."""
        self._check_started()
        value = max(-100.0, min(100.0, float(value)))
        if self._inverted:
            value = -value
        self._speed = value
        self._conn.send_command(cmd="set_motor", port=self._id, value=int(value * 100))

    @property
    def inverted(self) -> bool:
        """Whether the motor direction is inverted."""
        return self._inverted

    @inverted.setter
    def inverted(self, value: bool):
        """Set to True to flip the motor direction without rewiring."""
        self._inverted = bool(value)

    def stop(self):
        """Stop this motor immediately."""
        self.set_speed(0)

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
