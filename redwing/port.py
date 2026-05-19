"""Port abstraction — one physical connector on the robot board."""

from .devices.motor import Motor
from .devices.servo import Servo
from .devices.encoder import Encoder
from .devices.ultrasonic import Ultrasonic
from .devices.gpio import DigitalInput, DigitalOutput

# IDs 0–7 = single-pin (S0–S7), IDs 8–15 = dual-pin (D0–D7), ID 16 = I2C
_DUAL_ID_BASE = 8

# Device types that require two pins — only valid on dual-pin ports
_DUAL_PIN_ONLY = {"motor_sm", "encoder", "ultrasonic"}

def _port_name(port_id: int) -> str:
    """Return the human-readable port label (e.g. 'S3' or 'D1')."""
    if port_id >= _DUAL_ID_BASE:
        return f"D{port_id - _DUAL_ID_BASE}"
    return f"S{port_id}"


class Port:
    """Represents one physical port on the robot.

    Configure the port for the device you have plugged in::

        left_motor = robot.D0.motor()
        distance   = robot.D2.ultrasonic()
        arm        = robot.S0.servo()

    Each port can only be configured once.
    """

    def __init__(self, port_id: int, conn, dual_pin: bool):
        self._id = port_id
        self._conn = conn
        self._dual = dual_pin
        self._device = None

    @property
    def name(self) -> str:
        return _port_name(self._id)

    def _configure(self, port_type: str):
        if self._device is not None:
            raise RuntimeError(
                f"{self.name} is already configured as a "
                f"{type(self._device).__name__}. Each port can only be used for one device."
            )
        if port_type in _DUAL_PIN_ONLY and not self._dual:
            raise RuntimeError(
                f"{self.name} is a single-pin port and cannot be used for {port_type}. "
                f"Use a dual-pin port (D0–D7) for motors, encoders, and ultrasonic sensors."
            )
        self._conn.configure_port(self._id, port_type)

    # ------------------------------------------------------------------
    # Device factory methods
    # ------------------------------------------------------------------

    def motor(self, type: str = None) -> Motor:
        """Configure this port as a motor output and return a Motor object.

        Parameters
        ----------
        type:
            ``"sign_magnitude"`` (default on dual-pin ports) — two-wire direction + PWM.
            ``"servo_signal"``   (default on single-pin ports) — RC servo PWM signal,
                                  for motor controllers that accept a servo input.
            ``"locked_antiphase"`` — single PWM wire, duty cycle sets direction.

        Example::

            left = robot.D0.motor()          # sign-magnitude (dual-pin default)
            esc  = robot.S0.motor()          # servo signal (single-pin default)
            right = robot.D1.motor("locked_antiphase")
        """
        if type is None:
            type = "servo_signal" if not self._dual else "sign_magnitude"
        type_map = {
            "sign_magnitude": "motor_sm",
            "sm":             "motor_sm",
            "locked_antiphase": "motor_lap",
            "lap":              "motor_lap",
            "servo_signal":   "motor_servo_signal",
            "servo":          "motor_servo_signal",
        }
        if type not in type_map:
            raise ValueError(
                f"Unknown motor type '{type}'. "
                f"Choose from: 'sign_magnitude', 'locked_antiphase', 'servo_signal'."
            )
        port_type = type_map[type]
        self._configure(port_type)
        self._device = Motor(self._id, self._conn, port_type)
        return self._device

    def servo(
        self,
        min_deg: float = 0.0,
        max_deg: float = 300.0,
        min_us: int = 500,
        max_us: int = 2500,
    ) -> Servo:
        """Configure this port as an RC servo output and return a Servo object.

        Parameters
        ----------
        min_deg / max_deg:
            Degree range of the servo (default 0–300 for Redwing's servo).
            Use ``max_deg=180`` for a standard hobby servo.
        min_us / max_us:
            Pulse width in microseconds at the two extremes.

        Example — default 300° servo::

            arm = robot.S0.servo()
            arm.angle = 150  # center

        Example — standard 180° servo::

            arm = robot.S0.servo(max_deg=180, min_us=1000, max_us=2000)
            arm.angle = 90
        """
        self._configure("servo")
        self._device = Servo(
            self._id, self._conn,
            min_deg=min_deg, max_deg=max_deg,
            min_us=min_us, max_us=max_us,
        )
        return self._device

    def encoder(self) -> Encoder:
        """Configure this port as a quadrature encoder input and return an Encoder.

        Example::

            enc = robot.port2.encoder()
            left_motor.attach_encoder(enc)
        """
        self._configure("encoder")
        self._device = Encoder(self._id, self._conn)
        return self._device

    def ultrasonic(self) -> Ultrasonic:
        """Configure this port as an HC-SR04 ultrasonic sensor and return it.

        Example::

            sensor = robot.port3.ultrasonic()
            print(sensor.distance)   # cm
        """
        self._configure("ultrasonic")
        self._device = Ultrasonic(self._id, self._conn)
        return self._device

    def digital_input(self) -> DigitalInput:
        """Configure this port as a digital input (HIGH/LOW) and return it.

        Example::

            button = robot.port5.digital_input()
            if button.value:
                robot.log("Pressed!")
        """
        self._configure("gpio_in")
        self._device = DigitalInput(self._id, self._conn)
        return self._device

    def digital_output(self) -> DigitalOutput:
        """Configure this port as a digital output and return it.

        Example::

            led = robot.port6.digital_output()
            led.on()
        """
        self._configure("gpio_out")
        self._device = DigitalOutput(self._id, self._conn)
        return self._device

    @property
    def device(self):
        """The device currently configured on this port, or ``None``."""
        return self._device

    def __repr__(self):
        kind = type(self._device).__name__ if self._device else "unconfigured"
        pin_type = "dual-pin" if self._dual else "single-pin"
        return f"<{self.name} [{pin_type}] — {kind}>"
