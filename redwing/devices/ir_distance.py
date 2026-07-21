"""Sharp GP2Y0A21YK0F IR distance sensor (10–80 cm)."""

OUT_OF_RANGE = -1.0


class IrDistance:
    """Sharp GP2Y0A21YK0F (10–80 cm) analog IR distance sensor.

    Wire the sensor to **S5**, **S6**, or **S7** — these are the only
    S-ports with ADC hardware (GP26/ADC0, GP27/ADC1, GP28/ADC2).

    The sensor requires a **5V supply** (use the board's 5V rail, not 3.3V)
    and a **10 kΩ/10 kΩ voltage divider** between the sensor output and the
    port signal pin to keep the signal within the RP2040's 3.3V ADC limit.

    Example::

        sensor = robot.ir_distance(robot.S5)
        robot.start()

        while True:
            if sensor.in_range:
                robot.log(f"Distance: {sensor.distance:.1f} cm")
            robot.sleep(0.05)
    """

    def __init__(self, port_id: int, conn, robot=None):
        self._id = port_id
        self._conn = conn
        self._robot = robot

    def _check_started(self):
        if self._robot is not None and not self._robot._started:
            raise RuntimeError("Call robot.start() before reading sensor values.")

    @property
    def distance(self) -> float:
        """Distance in centimeters (10–80 cm).

        Returns ``-1`` if the reading is out of range or invalid.
        """
        self._check_started()
        state = self._conn.get_port_state(self._id)
        if not state.get("valid", False):
            return OUT_OF_RANGE
        mm = state.get("distance_mm", 0)
        return mm / 10.0 if mm > 0 else OUT_OF_RANGE

    @property
    def distance_mm(self) -> int:
        """Distance in millimeters. Returns ``-1`` if out of range."""
        self._check_started()
        state = self._conn.get_port_state(self._id)
        if not state.get("valid", False):
            return -1
        return state.get("distance_mm", -1)

    @property
    def in_range(self) -> bool:
        """``True`` if the sensor has a valid reading (10–80 cm)."""
        return self.distance >= 0
