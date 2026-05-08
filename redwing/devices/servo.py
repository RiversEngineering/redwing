"""RC servo control."""


class Servo:
    """Controls an RC servo motor.

    Angle ranges from 0 to 180 degrees, with 90 being center.

    Example::

        arm = robot.port5.servo()
        arm.angle = 0    # full left
        arm.angle = 90   # center
        arm.angle = 180  # full right
    """

    def __init__(self, port_id: int, conn, robot=None):
        self._id = port_id
        self._conn = conn
        self._angle = 90.0
        self._min_pulse_us = 1000
        self._max_pulse_us = 2000
        self._robot = robot

    def _check_started(self):
        if self._robot is not None and not self._robot._started:
            raise RuntimeError("Call robot.start() before setting servo angle.")

    @property
    def angle(self) -> float:
        """Current servo angle in degrees (0–180)."""
        return self._angle

    @angle.setter
    def angle(self, value: float):
        """Set servo angle in degrees. 0 = full left, 90 = center, 180 = full right."""
        self._check_started()
        value = max(0.0, min(180.0, float(value)))
        self._angle = value
        self._conn.send_command(cmd="set_servo", port=self._id, angle=int(value * 100))

    def center(self):
        """Move the servo to the center position (90 degrees)."""
        self.angle = 90.0

    def set_pulse_range(self, min_us: int = 1000, max_us: int = 2000):
        """Configure the servo pulse width range in microseconds.

        Most servos use 1000–2000 µs (the default). Some use 500–2500 µs.
        Adjust this if your servo does not reach its full range of motion.
        """
        self._min_pulse_us = min_us
        self._max_pulse_us = max_us
        self._conn.send_command(
            cmd="set_servo_range",
            port=self._id,
            min_us=min_us,
            max_us=max_us,
        )
