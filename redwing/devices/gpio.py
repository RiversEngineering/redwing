"""General-purpose digital I/O pins."""


class DigitalInput:
    """A single digital input pin.

    Reads HIGH (True) or LOW (False) from a digital signal.

    Example::

        button = robot.digital_input(robot.S1)
        if button.value:
            robot.log("Button pressed!")
    """

    def __init__(self, port_id: int, conn, robot=None):
        self._id = port_id
        self._conn = conn
        self._robot = robot

    def _check_started(self):
        if self._robot is not None and not self._robot._started:
            raise RuntimeError("Call robot.start() before reading digital inputs.")

    @property
    def value(self) -> bool:
        """Current pin state: ``True`` = HIGH, ``False`` = LOW."""
        self._check_started()
        return bool(self._conn.get_port_state(self._id).get("state", 0))

    def __bool__(self):
        return self.value


class DigitalOutput:
    """A single digital output pin.

    Controls a pin as HIGH or LOW.

    Example::

        led = robot.digital_output(robot.S2)
        led.on()
        led.off()
        led.value = True   # same as on()
    """

    def __init__(self, port_id: int, conn, robot=None):
        self._id = port_id
        self._conn = conn
        self._state = False
        self._robot = robot

    def _check_started(self):
        if self._robot is not None and not self._robot._started:
            raise RuntimeError("Call robot.start() before controlling digital outputs.")

    @property
    def value(self) -> bool:
        """Current output state."""
        return self._state

    @value.setter
    def value(self, state: bool):
        """Set output HIGH (True) or LOW (False)."""
        self._check_started()
        self._state = bool(state)
        self._conn.send_command(cmd="set_gpio", port=self._id, state=int(self._state))

    def on(self):
        """Set output HIGH."""
        self.value = True

    def off(self):
        """Set output LOW."""
        self.value = False

    def toggle(self):
        """Toggle the output state."""
        self.value = not self._state
