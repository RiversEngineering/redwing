"""Top-level Robot class — the entry point for all student code."""

from __future__ import annotations

import atexit
import time

from .connection import Connection
from .port import Port
from .devices.camera import Camera
from .devices.encoder import Encoder
from .devices.gamepad import Gamepad
from .devices.gpio import DigitalInput, DigitalOutput
from .devices.motor import Motor
from .devices.servo import Servo
from .devices.uart import UartBus
from .devices.ultrasonic import Ultrasonic
from .devices.lidar import Lidar
from .devices.tfmini import TFMini, TFLuna
from .devices.vl53l0x import VL53L0X

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
        All S ports are servo-capable (50 Hz hardware PWM).
        S5–S7 (GP26/ADC0, GP27/ADC1, GP28/ADC2) are also ADC-capable.

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
        self._gamepad = Gamepad(self._conn)
        self._uart_buses: dict[int, UartBus] = {}
        self._lidar: Lidar | None = None
        self._tfmini: dict[int, TFMini] = {}
        self._tfluna: dict[int, TFLuna] = {}
        self._vl53l0x: VL53L0X | None = None
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
        """Single-pin port S5 (GP26 — ADC0). PWM slice 5A — servo-capable."""
        return self._ports[5]

    @property
    def S6(self) -> Port:
        """Single-pin port S6 (GP27 — ADC1). PWM slice 5B — servo-capable."""
        return self._ports[6]

    @property
    def S7(self) -> Port:
        """Single-pin port S7 (GP28 — ADC2). PWM slice 6A — servo-capable."""
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

    @property
    def gamepad(self) -> Gamepad:
        """Access the gamepad controller.

        Works with the virtual controller on the iPad dashboard tab **and**
        with a physical USB/wireless gamepad (e.g. GameSir Nova Lite)
        connected to the Pi — no code change needed to switch between them.

        Example::

            while True:
                left.speed  = robot.gamepad.left_y * 100
                right.speed = robot.gamepad.left_y * 100
                robot.sleep(0.02)
        """
        return self._gamepad

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
        # Quick connectivity check: if the RP2040 has never sent a state packet
        # (ts == 0) it's not plugged in — give a clear error before trying to
        # finalize config, which would otherwise look like a PWM conflict.
        state = self._conn.get_all_state()
        if state.get("ts", 0) == 0:
            raise RuntimeError(
                "RP2040 not detected. Check that the Pico is plugged in "
                "via USB and that /dev/rp2040 is accessible."
            )

        ok, error = self._conn.finalize_config()
        if not ok:
            if "not responding" in error.lower() or not error:
                raise RuntimeError(
                    "RP2040 stopped responding during robot.start(). "
                    "Check the USB cable and try again."
                )
            raise RuntimeError(
                "Port configuration rejected by the RP2040. "
                "Check for PWM conflicts — motors and servos cannot share "
                "the same PWM slice (see dashboard log for which ports conflict)."
            )
        self._started = True

    # ------------------------------------------------------------------
    # UART bus (D7: GP12 = TX, GP13 = RX)
    # ------------------------------------------------------------------

    def uart(self, port: int = 15, baud: int = 115200) -> UartBus:
        """Configure *port* as a UART serial bus and return a :class:`UartBus` object.

        *port* must be **14** (D6, GP24=TX/GP25=RX, UART1) or **15** (D7,
        GP12=TX/GP13=RX, UART0, default).  Both ports can be configured
        simultaneously for two independent UART buses.

        Parameters
        ----------
        port:
            14 for D6 or 15 for D7 (default).
        baud:
            Baud rate in bits per second.  Common values: 9600, 115200 (default).

        Example::

            gps  = robot.uart(baud=9600)          # D7
            lidar_bus = robot.uart(port=14)        # D6, default 115200
        """
        if port not in (14, 15):
            raise ValueError("UART port must be 14 (D6) or 15 (D7).")
        self._check_not_started("configure UART")
        if port in self._uart_buses:
            return self._uart_buses[port]
        self._conn.configure_port(port, "uart", baud=baud)
        bus = UartBus(self._conn, robot=self, port_id=port)
        self._uart_buses[port] = bus
        self._ports[port]._device = bus
        return bus

    def uart1(self, baud: int = 115200) -> UartBus:
        """Convenience alias for ``robot.uart(port=14, baud=baud)`` (D6/UART1)."""
        return self.uart(port=14, baud=baud)

    # ------------------------------------------------------------------
    # TFMini / TFLuna UART LiDAR sensors (D6 or D7)
    # ------------------------------------------------------------------

    def tfmini(self, port: int = 15, baud: int = 115200) -> TFMini:
        """Configure *port* as UART and return a :class:`TFMini` LiDAR object.

        *port* must be **14** (D6, GP24/GP25) or **15** (D7, GP12/GP13, default).
        Call before ``robot.start()``.

        Wire the sensor **TX** pin to the board **RX** pin and vice versa.
        Both pins on the chosen port are claimed; the port cannot be used for
        motors or encoders at the same time.

        Parameters
        ----------
        port:
            14 for D6 (UART1) or 15 for D7 (UART0, default).
        baud:
            Baud rate — 115200 by default (TFMini factory default).

        Example::

            lidar = robot.tfmini()          # D7, 115200 baud
            robot.start()

            while True:
                if lidar.valid:
                    robot.log(f"Distance: {lidar.distance:.1f} cm")
                robot.sleep(0.02)
        """
        if port not in (14, 15):
            raise ValueError("TFMini port must be 14 (D6) or 15 (D7).")
        self._check_not_started("configure TFMini")
        if port not in self._tfmini:
            self._conn.configure_port(port, "uart", baud=baud)
            sensor = TFMini(self._conn, port_id=port)
            self._tfmini[port] = sensor
            self._ports[port]._device = sensor
        return self._tfmini[port]

    def tfluna(self, port: int = 15, baud: int = 115200) -> TFLuna:
        """Configure *port* as UART and return a :class:`TFLuna` LiDAR object.

        *port* must be **14** (D6, GP24/GP25) or **15** (D7, GP12/GP13, default).
        Call before ``robot.start()``.

        Wire the sensor **TX** pin to the board **RX** pin and vice versa.

        Parameters
        ----------
        port:
            14 for D6 (UART1) or 15 for D7 (UART0, default).
        baud:
            Baud rate — 115200 by default (TFLuna factory default).

        Example::

            lidar = robot.tfluna()          # D7, 115200 baud
            robot.start()

            while True:
                if lidar.valid:
                    robot.log(f"{lidar.distance:.1f} cm  {lidar.temperature:.1f} °C")
                robot.sleep(0.02)
        """
        if port not in (14, 15):
            raise ValueError("TFLuna port must be 14 (D6) or 15 (D7).")
        self._check_not_started("configure TFLuna")
        if port not in self._tfluna:
            self._conn.configure_port(port, "uart", baud=baud)
            sensor = TFLuna(self._conn, port_id=port)
            self._tfluna[port] = sensor
            self._ports[port]._device = sensor
        return self._tfluna[port]

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
    # VL53L0X I²C ToF sensor (auto-detected on GP4/GP5 at startup)
    # ------------------------------------------------------------------

    def vl53l0x(self) -> VL53L0X:
        """Return a :class:`VL53L0X` object for the I²C time-of-flight sensor.

        The sensor is wired to the dedicated I²C port (**GP4 SDA / GP5 SCL**)
        and is detected automatically by the firmware at startup — no
        configuration call is needed before ``robot.start()``.

        ``lidar.distance`` and other data properties raise
        :class:`RuntimeError` if the sensor is not detected.  Use
        ``lidar.connected`` to test presence without an exception.

        Example::

            lidar = robot.vl53l0x()
            robot.start()

            while True:
                if lidar.valid:
                    robot.log(f"Distance: {lidar.distance:.1f} cm")
                robot.sleep(0.02)
        """
        if self._vl53l0x is None:
            self._vl53l0x = VL53L0X(self._conn)
        return self._vl53l0x

    # ------------------------------------------------------------------
    # LIDAR (USB — connected directly to the Pi, not through the Pico)
    # ------------------------------------------------------------------

    def lidar(self, offset_deg: float = 0.0, max_cm: float = 400.0,
              x_offset_cm: float = 0.0, y_offset_cm: float = 0.0) -> Lidar:
        """Return a :class:`Lidar` object for the 360° USB LIDAR sensor.

        The LIDAR must be connected to the Raspberry Pi via USB and
        ``REDWING_LIDAR`` must be set to the serial port in ``docker-compose.yml``
        (e.g. ``REDWING_LIDAR: /dev/ttyUSB0``).

        Parameters
        ----------
        offset_deg:
            Clockwise rotation of the sensor's forward direction relative to
            the robot's forward direction.  Use this when the LIDAR is mounted
            at an angle so that all angles returned by the library are already
            in robot-relative coordinates.

            * ``0``   — sensor faces forward (default)
            * ``90``  — sensor rotated 90° clockwise
            * ``180`` — sensor faces backward
            * ``270`` — sensor rotated 90° counter-clockwise (or ``-90``)

        Example::

            lidar = robot.lidar()            # sensor points forward
            lidar = robot.lidar(offset=180)  # sensor mounted pointing backward

            while True:
                front = lidar.nearest_in_range(0, 45)   # always robot-forward
                if front < 30:
                    robot.stop()
                robot.sleep(0.1)
        """
        if self._lidar is None:
            self._lidar = Lidar(self._conn, offset_deg=offset_deg,
                                x_offset_cm=x_offset_cm, y_offset_cm=y_offset_cm)
            self._conn.send_command(
                cmd="set_lidar_config",
                offset=float(offset_deg),
                max_cm=float(max_cm),
                x_offset=float(x_offset_cm),
                y_offset=float(y_offset_cm),
            )
        return self._lidar

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def plot(self, label: str, value: float) -> None:
        """Send a named numeric value to the dashboard for real-time graphing.

        Call inside your loop to visualise any calculation alongside sensor
        data in the **Data** tab.  Each unique *label* becomes its own series.
        Values stream at whatever rate your loop runs.

        Parameters
        ----------
        label:
            Series name shown in the graph legend (e.g. ``"error"``).
        value:
            Any numeric value (int or float).

        Example::

            kp = 0.8
            while True:
                error = target - lidar.distance
                output = kp * error
                robot.plot("error", error)
                robot.plot("output", output)
                motor.speed = output
                robot.sleep(0.02)
        """
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise TypeError(
                f"robot.plot() value must be a number, got {type(value).__name__!r}"
            )
        self._conn.send_command(cmd="plot", label=str(label)[:64], value=v)

    # ------------------------------------------------------------------
    # Map — push world-frame data to the dashboard Map tab
    # ------------------------------------------------------------------

    def map_point(self, x: float, y: float) -> None:
        """Push one world-frame obstacle point to the dashboard map.

        Call inside your loop after transforming a LIDAR reading to world
        coordinates using your dead-reckoning pose estimate.

        Example::

            wx = pose_x + dist * math.sin(math.radians(pose_heading + angle))
            wy = pose_y + dist * math.cos(math.radians(pose_heading + angle))
            robot.map_point(wx, wy)
        """
        self._conn.send_command(cmd="map_point", x=float(x), y=float(y))

    def map_points(self, points) -> None:
        """Push multiple world-frame obstacle points at once (more efficient).

        *points* is any iterable of ``(x, y)`` pairs.  Use this to push
        an entire transformed LIDAR scan in a single command.

        Example::

            world_pts = [
                (pose_x + d * math.sin(math.radians(pose_hdg + a)),
                 pose_y + d * math.cos(math.radians(pose_hdg + a)))
                for a, d in lidar.scan()
            ]
            robot.map_points(world_pts)
        """
        self._conn.send_command(
            cmd="map_points",
            points=[[float(x), float(y)] for x, y in points],
        )

    def map_pose(self, x: float, y: float, heading_deg: float = 0.0) -> None:
        """Update the robot's estimated position on the dashboard map.

        The map tab shows a heading arrow at this position.  Call after
        updating your dead-reckoning estimate each loop.

        Parameters
        ----------
        x, y:
            World position in centimetres (same coordinate system as
            ``map_point``).
        heading_deg:
            Robot heading in degrees, 0° = forward, clockwise positive.

        Example::

            robot.map_pose(pose_x, pose_y, pose_heading)
        """
        self._conn.send_command(
            cmd="map_pose", x=float(x), y=float(y), heading=float(heading_deg)
        )

    def clear_map(self) -> None:
        """Clear all accumulated map points and pose from the dashboard."""
        self._conn.send_command(cmd="clear_map")

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
        """Pause the program for *seconds* and ensure fresh sensor data on return.

        Unlike ``time.sleep()``, this waits for the next state update from
        the daemon before returning (then sleeps any remaining time).  This
        guarantees that sensor reads immediately after ``robot.sleep()`` always
        reflect the latest values — even when the loop rate matches the
        daemon's 50 Hz broadcast interval.

        The total pause is always **at least** *seconds* long.

        Example::

            left.speed = 50
            robot.sleep(2)   # sleeps 2 s, reads fresh sensor data after
            left.stop()
        """
        t0 = time.monotonic()
        ev = self._conn._state_event
        ev.clear()                         # arm: catch the next state update
        ev.wait(timeout=seconds)           # wake early if state arrives
        elapsed = time.monotonic() - t0
        remaining = seconds - elapsed
        if remaining > 0.0005:             # skip sleeps shorter than 0.5 ms
            time.sleep(remaining)

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
