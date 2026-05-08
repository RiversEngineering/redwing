"""HC-SR04 ultrasonic distance sensor."""

OUT_OF_RANGE = -1.0


class Ultrasonic:
    """HC-SR04 ultrasonic distance sensor.

    Returns distance in centimeters. The sensor has a range of roughly
    2 cm to 400 cm. Readings outside that range return ``-1``.

    Example::

        sensor = robot.port3.ultrasonic()
        dist = sensor.distance      # centimeters, or -1 if out of range
        if sensor.in_range:
            print(f"Object is {dist:.1f} cm away")
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
        """Distance to the nearest object in centimeters.

        Returns ``-1`` if nothing is detected within range.
        """
        self._check_started()
        state = self._conn.get_port_state(self._id)
        mm = state.get("distance_mm", -1)
        if mm < 0 or not state.get("valid", False):
            return OUT_OF_RANGE
        return mm / 10.0

    @property
    def distance_mm(self) -> int:
        """Distance in millimeters. Returns ``-1`` if out of range."""
        state = self._conn.get_port_state(self._id)
        if not state.get("valid", False):
            return -1
        return state.get("distance_mm", -1)

    @property
    def in_range(self) -> bool:
        """``True`` if the sensor has a valid reading."""
        return self.distance >= 0
