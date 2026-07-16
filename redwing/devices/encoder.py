"""Quadrature encoder input."""


class Encoder:
    """Reads a quadrature encoder for measuring motor position and speed.

    Attach to a motor with ``motor.attach_encoder(encoder)`` to enable
    closed-loop velocity control.

    Example::

        enc = robot.port2.encoder()
        print(enc.count)      # total ticks since last reset
        print(enc.velocity)   # ticks per second
        enc.reset()           # set count back to zero
    """

    def __init__(self, port_id: int, conn, robot=None):
        self._id = port_id
        self._conn = conn
        self._robot = robot
        self._inverted = False

    def _check_started(self):
        if self._robot is not None and not self._robot._started:
            raise RuntimeError("Call robot.start() before reading encoder values.")

    @property
    def inverted(self) -> bool:
        """Whether the encoder count direction is inverted.

        Set to True when positive motor output produces a decreasing encoder
        count — for example, when the motor is physically mounted or wired in
        reverse.  Inversion is applied in firmware so both user reads and PID
        loops see the corrected sign.

        Check this as part of motor/encoder setup before enabling PID: run the
        motor forward at low power, observe whether the count increases. If it
        decreases, set ``encoder.inverted = True``.

        Example::

            shoulder_enc.inverted = True   # down is positive for this arm
        """
        return self._inverted

    @inverted.setter
    def inverted(self, value: bool):
        self._inverted = bool(value)
        self._conn.send_command(cmd="invert_encoder", port=self._id, inverted=self._inverted)

    @property
    def count(self) -> int:
        """Total encoder ticks since the last reset. Increases going forward,
        decreases going backward (depending on motor wiring)."""
        self._check_started()
        return self._conn.get_port_state(self._id).get("count", 0)

    @property
    def velocity(self) -> float:
        """Encoder velocity in ticks per second. Positive = forward."""
        self._check_started()
        raw = self._conn.get_port_state(self._id).get("velocity", 0)
        return raw / 10.0

    def reset(self):
        """Reset the encoder tick count to zero."""
        self._check_started()
        self._conn.send_command(cmd="reset_encoder", port=self._id)
