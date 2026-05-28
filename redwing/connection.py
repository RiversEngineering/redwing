"""Manages ZeroMQ connection between student code and the Redwing daemon."""

import base64
import json
import threading
import time

import zmq

STATE_PORT = 5555    # daemon PUB  →  library SUB
CMD_PORT   = 5556    # library PUSH →  daemon PULL
CFG_PORT   = 5557    # library REQ  ↔  daemon REP

CONNECT_TIMEOUT_MS = 3000


class Connection:
    def __init__(self, host: str = "localhost"):
        self._ctx = zmq.Context()

        self._sub = self._ctx.socket(zmq.SUB)
        self._sub.connect(f"tcp://{host}:{STATE_PORT}")
        self._sub.setsockopt_string(zmq.SUBSCRIBE, "")
        self._sub.setsockopt(zmq.RCVTIMEO, 100)

        self._push = self._ctx.socket(zmq.PUSH)
        self._push.setsockopt(zmq.SNDHWM, 4)  # drop commands if backlogged; prevents stale queue lag
        self._push.connect(f"tcp://{host}:{CMD_PORT}")

        self._req = self._ctx.socket(zmq.REQ)
        self._req.connect(f"tcp://{host}:{CFG_PORT}")
        self._req.setsockopt(zmq.RCVTIMEO, CONNECT_TIMEOUT_MS)
        self._req.setsockopt(zmq.SNDTIMEO, CONNECT_TIMEOUT_MS)

        self._state: dict = {"ports": {}}
        self._lock = threading.Lock()
        self._uart_rx_bufs: dict[int, bytearray] = {14: bytearray(), 15: bytearray()}
        self._state_event = threading.Event()   # set each time a new state arrives
        self._connected = False
        self._running = True

        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

        self._wait_for_connection(host)

    def _wait_for_connection(self, host: str):
        deadline = time.monotonic() + CONNECT_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            with self._lock:
                if self._connected:
                    return
            time.sleep(0.05)
        raise ConnectionError(
            f"Could not connect to the Redwing daemon at {host}. "
            "Make sure the daemon is running before starting your program."
        )

    def _recv_loop(self):
        while self._running:
            try:
                msg = self._sub.recv_json()
                with self._lock:
                    # Route per-port UART RX bytes into their buffers
                    uart_rx = msg.pop("uart_rx", None)
                    if isinstance(uart_rx, dict):
                        for pid_str, b64 in uart_rx.items():
                            pid = int(pid_str)
                            if pid in self._uart_rx_bufs:
                                self._uart_rx_bufs[pid].extend(base64.b64decode(b64))
                    elif isinstance(uart_rx, (str, bytes)) and uart_rx:
                        # Legacy single-buffer fallback — assume D7
                        self._uart_rx_bufs[15].extend(base64.b64decode(uart_rx))
                    self._state = msg
                    self._connected = True
                self._state_event.set()  # wake any robot.sleep() waiting for fresh data
            except zmq.Again:
                pass
            except zmq.ZMQError:
                break

    def get_port_state(self, port_id: int) -> dict:
        with self._lock:
            return self._state.get("ports", {}).get(str(port_id), {})

    def get_all_state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def send_command(self, **kwargs):
        try:
            self._push.send_json(kwargs, zmq.NOBLOCK)
        except zmq.Again:
            pass

    def reset(self):
        """Tell the daemon to reset the RP2040 state for a new student program.

        Best-effort: if the RP2040 is not connected yet, the reset is skipped and
        the program continues normally (the RP2040 will be in a clean state anyway).
        """
        try:
            self._req.send_json({"cmd": "reset"})
            self._req.recv_json()
        except zmq.ZMQError:
            pass  # daemon or RP2040 not ready — not fatal at startup

    def finalize_config(self) -> bool:
        """Send CMD_CONFIG_DONE and wait for the RP2040 to validate the configuration."""
        self._req.setsockopt(zmq.RCVTIMEO, 8000)
        try:
            self._req.send_json({"cmd": "finalize"})
            reply = self._req.recv_json()
        except zmq.ZMQError as e:
            raise ConnectionError(
                "Lost connection to the Redwing daemon during robot.start()."
            ) from e
        finally:
            self._req.setsockopt(zmq.RCVTIMEO, CONNECT_TIMEOUT_MS)
        return bool(reply.get("ok", False))

    def configure_port(self, port_id: int, port_type: str, **extra):
        req = {"cmd": "configure", "port": port_id, "type": port_type, **extra}
        try:
            self._req.send_json(req)
            reply = self._req.recv_json()
        except zmq.ZMQError as e:
            raise ConnectionError(
                f"Lost connection to the Redwing daemon while configuring port {port_id}."
            ) from e

        if not reply.get("ok"):
            raise RuntimeError(
                f"Could not configure port {port_id}: {reply.get('error', 'unknown error')}"
            )

    # ------------------------------------------------------------------
    # UART helpers (used by UartBus)
    # ------------------------------------------------------------------

    def read_uart_bytes(self, n: int = -1, port_id: int = 15) -> bytes:
        """Return up to *n* bytes from the UART RX buffer for *port_id* (non-blocking)."""
        with self._lock:
            buf = self._uart_rx_bufs.get(port_id)
            if buf is None:
                return b""
            if n < 0 or n >= len(buf):
                data = bytes(buf)
                buf.clear()
            else:
                data = bytes(buf[:n])
                del buf[:n]
        return data

    def read_uart_until(self, terminator: bytes, timeout: float = 1.0, port_id: int = 15) -> bytes | None:
        """Read from the UART RX buffer for *port_id* until *terminator* or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                buf = self._uart_rx_bufs.get(port_id)
                if buf is not None:
                    idx = buf.find(terminator)
                    if idx >= 0:
                        data = bytes(buf[:idx])
                        del buf[:idx + len(terminator)]
                        return data
            time.sleep(0.01)
        return None

    def close(self):
        self._running = False
        self._thread.join(timeout=1.0)
        self._sub.close()
        self._push.close()
        self._req.close()
        self._ctx.term()
