"""UART bus device — serial communication through S0 (TX) and S1 (RX)."""

import base64
import time


class UartBus:
    """A UART serial bus connected to S0 (TX) and S1 (RX) on the Pico.

    Obtain via ``robot.uart()``::

        uart = robot.uart(baud=9600)
        uart.write("AT\\r\\n")
        response = uart.readline(timeout=1.0)
    """

    def __init__(self, conn, robot=None, port_id: int = 15):
        self._conn    = conn
        self._robot   = robot
        self._port_id = port_id

    def _check_started(self):
        if self._robot is not None and not self._robot._started:
            raise RuntimeError("Call robot.start() before using the UART bus.")

    def write(self, data: bytes | str) -> None:
        """Send bytes (or a string, which is UTF-8 encoded) over UART.

        Example::

            uart.write(b"\\x02\\x10")       # raw bytes
            uart.write("HELLO\\r\\n")        # string → UTF-8
        """
        self._check_started()
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._conn.send_command(
            cmd="uart_tx",
            port=self._port_id,
            data=base64.b64encode(data).decode(),
        )

    def read(self, n: int = -1) -> bytes:
        """Read up to *n* bytes that have been received so far (non-blocking).

        Passing ``n=-1`` (default) returns all buffered bytes.

        Example::

            chunk = uart.read(4)
        """
        self._check_started()
        return self._conn.read_uart_bytes(n, port_id=self._port_id)

    def readline(self, timeout: float = 1.0) -> str | None:
        """Read one line (up to the next ``\\n``) and return it decoded as UTF-8.

        Returns ``None`` if no complete line arrives within *timeout* seconds.

        Example::

            line = uart.readline(timeout=2.0)
            if line:
                robot.log("Got:", line)
        """
        data = self._conn.read_uart_until(b"\n", timeout, port_id=self._port_id)
        if data is None:
            return None
        return data.decode("utf-8", errors="replace").strip()

    def read_bytes_until(self, terminator: bytes, timeout: float = 1.0) -> bytes | None:
        """Read until *terminator* bytes are seen or *timeout* elapses.

        Returns the data before the terminator, or ``None`` on timeout.
        """
        return self._conn.read_uart_until(terminator, timeout, port_id=self._port_id)
