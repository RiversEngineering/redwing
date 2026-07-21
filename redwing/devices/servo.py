"""RC servo control."""

import time


class Servo:
    """Controls an RC servo motor.

    The servo range is configurable. Redwing's default servo has a 300° range
    (500–2500 µs pulse width). Standard hobby servos typically use 180°
    (1000–2000 µs).

    Example — default 300° servo::

        arm = robot.S0.servo()
        arm.set_angle(0)    # full counterclockwise
        arm.set_angle(150)  # center
        arm.set_angle(300)  # full clockwise

    Example — standard 180° servo::

        arm = robot.S0.servo(max_deg=180, min_us=1000, max_us=2000)
        arm.set_angle(90)   # center
    """

    def __init__(
        self,
        port_id: int,
        conn,
        robot=None,
        min_deg: float = 0.0,
        max_deg: float = 300.0,
        min_us: int = 500,
        max_us: int = 2500,
    ):
        self._id = port_id
        self._conn = conn
        self._robot = robot
        self._min_deg = float(min_deg)
        self._max_deg = float(max_deg)
        self._min_us = int(min_us)
        self._max_us = int(max_us)
        self._angle = (self._min_deg + self._max_deg) / 2

    def _deg_to_us(self, deg: float) -> int:
        lo, hi = sorted((self._min_deg, self._max_deg))
        deg = max(lo, min(hi, deg))
        t = (deg - self._min_deg) / (self._max_deg - self._min_deg)
        return int(self._min_us + t * (self._max_us - self._min_us))

    def _check_started(self):
        if self._robot is not None and not self._robot._started:
            raise RuntimeError("Call robot.start() before commanding the servo.")

    @property
    def angle(self) -> float:
        """Last commanded angle in degrees."""
        return self._angle

    def set_angle(self, deg: float):
        """Command the servo to move to the given angle in degrees."""
        self._check_started()
        self._angle = max(self._min_deg, min(self._max_deg, float(deg)))
        self._conn.send_command(
            cmd="set_servo", port=self._id, pulse_us=self._deg_to_us(self._angle)
        )

    def center(self):
        """Move the servo to the center of its configured range."""
        self.set_angle((self._min_deg + self._max_deg) / 2)

    def set_gobilda_mode(self, mode: str):
        """Switch a GoBilda dual-mode servo between 'positional' and 'continuous' rotation.

        Sends the mode-switch command to the firmware, which performs a half-duplex
        UART handshake (~420 ms) before the servo reboots.  This method blocks for
        600 ms to let the full sequence complete before returning.

        Only works on S-port servos (S0–S7).  Has no effect on PCA9685 channels.
        """
        self._check_started()
        self._conn.send_command(cmd="gobilda_set_mode", port=self._id, mode=mode)
        time.sleep(0.6)
