"""Top-level Robot class — the entry point for all student code."""

from __future__ import annotations

import atexit
import time

from .connection import Connection
from .port import Port
from .devices.camera import Camera
from .devices.encoder import Encoder
from .devices.gpio import DigitalInput, DigitalOutput
from .devices.motor import Motor
from .devices.servo import Servo
from .devices.uart import UartBus
from .devices.ultrasonic import Ultrasonic
from .devices.lidar import Lidar

# Single-pin ports S0–S7 → internal IDs 0–7
# Dual-pin ports   D0–D7 → internal IDs 8–15
# Dedicated I2C port     → internal ID  16
_SINGLE_IDS = range(0, 8)
_DUAL_IDS   = range(8, 16)
_I2C_ID     = 16


class Robot:
    """The main robot object. Create one at the start of your program.

    Example::

        import redwing

        robot = redwing.Robot()

        left   = robot.D0.motor()
        right  = robot.D1.motor()
        right.inverted = True          # flip direction without rewiring

        sensor = robot.D2.ultrasonic()
        arm    = robot.S0.servo()

        while True:
            if sensor.distance < 20:
                left.stop()
                right.stop()
            else:
                left.speed  = 60
                right.speed = 60

    **Single-pin ports S0–S7** (one wire):
        S0–S4: servos, digital I/O, locked-antiphase motors (PWM slices 0,0,1,1,3).
        S5–S7 (GP26/ADC0, GP27/ADC1, GP28/ADC2): digital I/O and analog input only.
        S5–S7 cannot be servos — their PWM slices conflict with motor ports D2/D3/D7.

    **Dual-pin ports D0–D7** (two wires, labeled A and B):
        Sign-magnitude motors, quadrature encoders, ultrasonic sensors.
        All motor speed pins (B) use PWM slices 4–7 (20 kHz), so motors
        and servos (S0–S4) never conflict.
        D6 (GP24/GP25) also serves as UART1 when ``robot.uart1()`` is called.
        D7 (GP12/GP13) also serves as UART0 when ``robot.uart()`` is called.

    **Dedicated I2C port** (SDA / SCL, always GP4 / GP5):
        Reserved for I2C sensors (IMUs, ToF sensors, etc.).
        Cannot be used as a general-purpose port.
    """

    def __init__(self, host: str = "localhost"):
        """Connect to the Redwing daemon.

        Parameters
        ----------
        host:
            Hostname or IP of the Pi. Defaults to ``"localhost"``.
        """
        self._conn = Connection(host)
        self._ports: dict[int, Port] = {}
        for i in _SINGLE_IDS:
            self._ports[i] = Port(i, self._conn, dual_pin=False)
        for i in _DUAL_IDS:
            self._ports[i] = Port(i, self._conn, dual_pin=True)
        self._camera = Camera(self._conn)
        self._uart: UartBus | None = None
        self._lidar: Lidar | None = None
        self._started = False
        atexit.register(self._shutdown)
        # Reset RP2040 state from any previous run (best-effort; no-op if not connected)
        self._conn.reset()

    # ------------------------------------------------------------------
    # Single-pin port properties (S0–S7)
    # Explicit properties give students IDE autocomplete.
    # ------------------------------------------------------------------

    @property
    def S0(self) -> Port:
        """Single-pin port S0 (GP0). PWM slice 0A (50 Hz servo-capable)."""
        return self._ports[0]

    @property
    def S1(self) -> Port:
        """Single-pin port S1 (GP1). PWM slice 0B (50 Hz servo-capable)."""
        return self._ports[1]

    @property
    def S2(self) -> Port:
        """Single-pin port S2 (GP2). PWM slice 1A."""
        return self._ports[2]

    @property
    def S3(self) -> Port:
        """Single-pin port S3 (GP3). PWM slice 1B."""
        return self._ports[3]

    @property
    def S4(self) -> Port:
        """Single-pin port S4 (GP6). PWM slice 3A."""
        return self._ports[4]

    @property
    def S5(self) -> Port:
        """Single-pin port S5 (GP26 — ADC0). GPIO and analog input only. Not servo-capable."""
        return self._ports[5]

    @property
    def S6(self) -> Port:
        """Single-pin port S6 (GP27 — ADC1). GPIO and analog input only. Not servo-capable."""
        return self._ports[6]

    @property
    def S7(self) -> Port:
        """Single-pin port S7 (GP28 — ADC2). GPIO and analog input only. Not servo-capable."""
        return self._ports[7]

    # ------------------------------------------------------------------
    # Dual-pin port properties (D0–D7)
    # All B pins are on PWM slices 4–7 (20 kHz motor range).
    # ------------------------------------------------------------------

    @property
    def D0(self) -> Port:
        """Dual-pin port D0 (GP16 A / GP8 B). B pin: PWM slice 4A."""
        return self._ports[8]

    @property
    def D1(self) -> Port:
        """Dual-pin port D1 (GP17 A / GP9 B). B pin: PWM slice 4B."""
        return self._ports[9]

    @property
    def D2(self) -> Port:
        """Dual-pin port D2 (GP18 A / GP10 B). B pin: PWM slice 5A."""
        return self._ports[10]

    @property
    def D3(self) -> Port:
        """Dual-pin port D3 (GP19 A / GP11 B). B pin: PWM slice 5B."""
        return self._ports[11]

    @property
    def D4(self) -> Port:
        """Dual-pin port D4 (GP22 A / GP15 B). B pin: PWM slice 7B."""
        return self._ports[12]

    @property
    def D5(self) -> Port:
        """Dual-pin port D5 (GP20 A / GP14 B). B pin: PWM slice 7A."""
        return self._ports[13]

    @property
    def D6(self) -> Port:
        """Dual-pin port D6 (GP24 A / GP25 B). B pin: PWM slice 4B (PIO PWM when motor).
        Also serves as UART1 when ``robot.uart1()`` is called (GP24=TX, GP25=RX).
        """
        return self._ports[14]

    @property
    def D7(self) -> Port:
        """Dual-pin port D7 (GP12 A / GP13 B). B pin: PWM slice 6B.
        Also serves as UART0 when ``robot.uart()`` is called (GP12=TX, GP13=RX).
        """
        return self._ports[15]

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------

    @property
    def camera(self) -> Camera:
        """Access the robot's webcam.

        Example::

            frame = robot.camera.read()
            robot.camera.show(frame)
        """
        return self._camera

    # ------------------------------------------------------------------
    # Device factory methods — call these during setup, before start()
    # ------------------------------------------------------------------

    def _check_not_started(self, action: str = "configure a port"):
        if self._started:
            raise RuntimeError(
                f"Cannot {action} after robot.start(). "
                "Move all device setup calls above robot.start()."
            )

    def motor(self, port: Port, type: str = "sign_magnitude") -> Motor:
        """Configure *port* as a DC motor output and return a Motor object.

        Parameters
        ----------
        port:
            A dual-pin port (``robot.D0`` – ``robot.D7``).
        type:
            ``"sign_magnitude"`` (default) — direction + PWM speed.
            ``"locked_antiphase"``          — single PWM wire.
            ``"servo_signal"``              — RC-servo-style PWM signal.

        Example::

            left  = robot.motor(robot.D0)
            right = robot.motor(robot.D1)
            right.inverted = True
            robot.start()
            left.speed = 60
        """
        self._check_not_started("configure a motor")
        type_map = {
            "sign_magnitude":  "motor_sm",
            "sm":              "motor_sm",
            "locked_antiphase":"motor_lap",
            "lap":             "motor_lap",
            "servo_signal":    "motor_servo_signal",
            "servo":           "motor_servo_signal",
        }
        if type not in type_map:
            raise ValueError(
                f"Unknown motor type '{type}'. "
                "Choose from: 'sign_magnitude', 'locked_antiphase', 'servo_signal'."
            )
        port_type = type_map[type]
        port._configure(port_type)
        device = Motor(port._id, self._conn, port_type, robot=self)
        port._device = device
        return device

    def servo(self, port: Port) -> Servo:
        """Configure *port* as an RC servo and return a Servo object.

        S5 (GP26/ADC0), S6 (GP27/ADC1), and S7 (GP28/ADC2) cannot be used as servos —
        they share PWM slices with motor ports D2, D3, and D7 respectively.

        Example::

            arm = robot.servo(robot.S0)
            robot.start()
            arm.angle = 90
        """
        self._check_not_started("configure a servo")
        if port._id in (5, 6, 7):
            names = {5: "S5 (GP26/ADC0)", 6: "S6 (GP27/ADC1)", 7: "S7 (GP28/ADC2)"}
            raise ValueError(
                f"{names[port._id]} cannot be used as a servo. "
                "S5/S6/S7 are ADC pins whose PWM slices conflict with motor ports D2/D3/D7. "
                "Use S0–S4 for servos, or use this port as digital_input/digital_output."
            )
        port._configure("servo")
        device = Servo(port._id, self._conn, robot=self)
        port._device = device
        return device

    def encoder(self, port: Port) -> Encoder:
        """Configure *port* as a quadrature encoder input and return an Encoder.

        Example::

            enc   = robot.encoder(robot.D2)
            left  = robot.motor(robot.D0)
            robot.start()
            left.attach_encoder(enc)
        """
        self._check_not_started("configure an encoder")
        port._configure("encoder")
        device = Encoder(port._id, self._conn, robot=self)
        port._device = device
        return device

    def ultrasonic(self, port: Port) -> Ultrasonic:
        """Configure *port* as an HC-SR04 ultrasonic distance sensor.

        Example::

            sensor = robot.ultrasonic(robot.D3)
            robot.start()
            print(sensor.distance)   # cm
        """
        self._check_not_started("configure an ultrasonic sensor")
        port._configure("ultrasonic")
        device = Ultrasonic(port._id, self._conn, robot=self)
        port._device = device
        return device

    def digital_input(self, port: Port) -> DigitalInput:
        """Configure *port* as a digital input and return a DigitalInput object.

        Example::

            button = robot.digital_input(robot.S3)
            robot.start()
            if button.value:
                robot.log("Pressed!")
        """
        self._check_not_started("configure a digital input")
        port._configure("gpio_in")
        device = DigitalInput(port._id, self._conn, robot=self)
        port._device = device
        return device

    def digital_output(self, port: Port) -> DigitalOutput:
        """Configure *port* as a digital output and return a DigitalOutput object.

        Example::

            led = robot.digital_output(robot.S4)
            robot.start()
            led.on()
        """
        self._check_not_started("configure a digital output")
        port._configure("gpio_out")
        device = DigitalOutput(port._id, self._conn, robot=self)
        port._device = device
        return device

    # ------------------------------------------------------------------
    # Start — finalizes configuration and enables runtime commands
    # ------------------------------------------------------------------

    def start(self):
        """Finalize port configuration and enable motor/sensor commands.

        Call this once after creating all devices with ``robot.motor()``,
        ``robot.servo()``, etc.  The RP2040 validates the configuration
        (checking for PWM conflicts) and locks it in.  All motor and sensor
        commands will raise an error if called before ``robot.start()``.

        Raises
        ------
        RuntimeError
            If the RP2040 rejects the configuration (e.g. PWM slice conflict
            between a motor and a servo on the same port pair).

        Example::

            left   = robot.motor(robot.D0)
            arm    = robot.servo(robot.S0)
            sensor = robot.ultrasonic(robot.D2)
            robot.start()           # ← everything above this is setup

            while True:
                left.speed = 60
        """
        ok = self._conn.finalize_config()
        if not ok:
            raise RuntimeError(
                "Port configuration rejected by the RP2040. "
                "Check for PWM conflicts — motors and servos cannot share "
                "the same PWM slice (see dashboard log for which ports conflict)."
            )
        self._started = True

    # ------------------------------------------------------------------
    # UART bus (D7: GP12 = TX, GP13 = RX)
    # ------------------------------------------------------------------

    def uart(self, baud: int = 115200) -> UartBus:
        """Configure D7 as a UART serial bus and return a UartBus object.

        D7 is reserved once UART is configured — it cannot be used as a motor
        or encoder port.  The bus uses GP12 as TX and GP13 as RX (UART0).

        Parameters
        ----------
        baud:
            Baud rate (bits per second).  Common values: 9600, 115200 (default).

        Example::

            gps = robot.uart(baud=9600)
            line = gps.readline(timeout=2.0)
            robot.log("GPS:", line)
        """
        self._check_not_started("configure UART")
        if self._uart is not None:
            return self._uart
        self._conn.configure_port(15, "uart", baud=baud)
        self._uart = UartBus(self._conn, robot=self)
        self._ports[15]._device = self._uart
        return self._uart

    # ------------------------------------------------------------------
    # Dedicated I2C port (GP4 SDA / GP5 SCL, always reserved)
    # ------------------------------------------------------------------

    @property
    def i2c_port(self) -> int:
        """Internal port ID of the dedicated I2C connector (GP4 SDA / GP5 SCL).

        These pins are always reserved as I2C0 and cannot be used for anything else.
        High-level I2C device support (IMU, ToF, etc.) will be added in a future release.
        """
        return _I2C_ID

    # ------------------------------------------------------------------
    # LIDAR (USB — connected directly to the Pi, not through the Pico)
    # ------------------------------------------------------------------

    def lidar(self) -> Lidar:
        """Return a Lidar object for the 360° USB LIDAR sensor.

        The LIDAR must be connected to the Raspberry Pi via USB and
        ``REDWING_LIDAR`` must be set to the serial port (e.g. ``/dev/ttyUSB0``).

        Example::

            lidar = robot.lidar()

            while True:
                if lidar.nearest() < 30:
                    robot.stop()
                robot.sleep(0.1)
        """
        if self._lidar is None:
            self._lidar = Lidar(self._conn)
        return self._lidar

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def log(self, *args, level: str = "info"):
        """Send a message to the dashboard debug console.

        Works like ``print()`` — pass any number of values.

        Example::

            robot.log("Starting up!")
            robot.log("Distance:", sensor.distance, "cm")
        """
        message = " ".join(str(a) for a in args)
        self._conn.send_command(cmd="log", level=level, message=message)

    def stop(self):
        """Stop all motors immediately."""
        self._conn.send_command(cmd="stop_all")

    def sleep(self, seconds: float):
        """Pause the program for the given number of seconds.

        Example::

            left.speed = 50
            robot.sleep(2)
            left.stop()
        """
        time.sleep(seconds)

    @property
    def uptime(self) -> float:
        """Seconds since the daemon started."""
        return self._conn.get_all_state().get("uptime", 0.0)

    def _shutdown(self):
        try:
            self.stop()
        except Exception:
            pass
        self._conn.close()
