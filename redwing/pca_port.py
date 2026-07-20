"""PCA9685 channel abstraction — mirrors the Port API for the I²C PWM expander."""


class PcaMotor:
    """Controls a brushed DC motor via the PCA9685 I²C PWM expander.

    Power is set as a percentage: -100 (full reverse) to +100 (full forward).
    Uses the RC ESC signalling protocol: 1500 µs = stop, 1100 µs = full reverse,
    1900 µs = full forward.

    Example::

        m = robot.P0.motor()
        m.set_power(75)
    """

    def __init__(self, channel: int, conn, robot=None):
        self._channel = channel
        self._conn = conn
        self._robot = robot
        self._power = 0.0
        self._inverted = False

    def _check_started(self):
        if self._robot is not None and not self._robot._started:
            raise RuntimeError(
                "Call robot.start() before setting motor power."
            )

    @property
    def power(self) -> float:
        """Last commanded power as a percentage from -100 to +100."""
        return self._power

    def set_power(self, value: float):
        """Set motor power from -100 (full reverse) to +100 (full forward)."""
        self._check_started()
        value = max(-100.0, min(100.0, float(value)))
        if self._inverted:
            value = -value
        self._power = value
        self._conn.send_command(cmd="pca_set_motor", channel=self._channel, value=int(value * 100))

    def stop(self):
        """Stop this motor immediately."""
        self.set_power(0)

    @property
    def inverted(self) -> bool:
        return self._inverted

    @inverted.setter
    def inverted(self, value: bool):
        self._inverted = bool(value)


class PcaServo:
    """Controls an RC servo via the PCA9685 I²C PWM expander.

    Example::

        arm = robot.P1.servo()
        arm.angle = 150   # center
    """

    def __init__(self, channel: int, conn,
                 min_deg: float = 0.0, max_deg: float = 300.0,
                 min_us: int = 500, max_us: int = 2500):
        self._channel = channel
        self._conn = conn
        self._min_deg = min_deg
        self._max_deg = max_deg
        self._min_us = min_us
        self._max_us = max_us
        self._angle = (min_deg + max_deg) / 2.0

    def _deg_to_us(self, deg: float) -> int:
        deg = max(self._min_deg, min(self._max_deg, deg))
        frac = (deg - self._min_deg) / (self._max_deg - self._min_deg)
        return int(self._min_us + frac * (self._max_us - self._min_us))

    @property
    def angle(self) -> float:
        return self._angle

    @angle.setter
    def angle(self, deg: float):
        deg = max(self._min_deg, min(self._max_deg, float(deg)))
        self._angle = deg
        pulse_us = self._deg_to_us(deg)
        self._conn.send_command(cmd="pca_set_servo", channel=self._channel, pulse_us=pulse_us)

    def set_angle(self, deg: float):
        self.angle = deg


class PcaPort:
    """Represents one channel on the PCA9685 PWM expander (P0–P15).

    Because the PCA9685 runs all channels at 50 Hz, it only supports
    servo-style outputs (servos and RC ESC motor controllers).

    Example::

        left  = robot.P0.motor()
        right = robot.P1.motor()
        arm   = robot.P2.servo()
    """

    def __init__(self, channel: int, conn, robot=None):
        self._channel = channel
        self._conn = conn
        self._robot = robot
        self._device = None

    @property
    def name(self) -> str:
        return f"P{self._channel}"

    def _configure(self, port_type: str):
        if self._device is not None:
            raise RuntimeError(
                f"P{self._channel} is already configured as a "
                f"{type(self._device).__name__}. Each port can only be used for one device."
            )
        self._conn.configure_pca_channel(self._channel, port_type)

    def motor(self) -> PcaMotor:
        """Configure this PCA channel as an RC ESC motor output.

        Uses 1500 µs = stop, 1100 µs = full reverse, 1900 µs = full forward.

        Example::

            m = robot.P0.motor()
            m.set_power(100)   # full forward
        """
        self._configure("motor_servo_signal")
        self._device = PcaMotor(self._channel, self._conn, robot=self._robot)
        return self._device

    def servo(self,
              min_deg: float = 0.0, max_deg: float = 300.0,
              min_us: int = 500, max_us: int = 2500) -> PcaServo:
        """Configure this PCA channel as an RC servo output.

        Parameters
        ----------
        min_deg / max_deg:
            Degree range of the servo (default 0–300).
        min_us / max_us:
            Pulse width in microseconds at the extremes.

        Example::

            arm = robot.P1.servo(max_deg=180, min_us=1000, max_us=2000)
            arm.angle = 90
        """
        self._configure("servo")
        self._conn.send_command(
            cmd="set_pca_servo_range",
            channel=self._channel,
            min_angle=min_deg,
            max_angle=max_deg,
            min_us=min_us,
            max_us=max_us,
        )
        self._device = PcaServo(self._channel, self._conn, min_deg, max_deg, min_us, max_us)
        return self._device

    @property
    def device(self):
        return self._device

    def __repr__(self):
        kind = type(self._device).__name__ if self._device else "unconfigured"
        return f"<P{self._channel} [PCA9685] — {kind}>"
