"""Manages async serial communication with the RP2040."""

import asyncio
import logging

import serial_asyncio

from . import protocol as proto
from .config import SERIAL_PORT, SERIAL_BAUD, STREAM_HZ
from .state import SharedState

log = logging.getLogger(__name__)

RECONNECT_DELAY = 2.0


class RP2040:
    def __init__(self, state: SharedState):
        self._state = state
        self._writer: asyncio.StreamWriter | None = None
        self._cmd_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._parser = proto.PacketParser()
        self._connected = False
        self._config_done_future: asyncio.Future | None = None
        self._reset_future: asyncio.Future | None = None
        self._measure_pulse_future: asyncio.Future | None = None

    async def run(self):
        while True:
            try:
                await self._connect_and_run()
            except Exception as e:
                log.warning(f"RP2040 disconnected: {e}. Reconnecting in {RECONNECT_DELAY}s...")
                self._connected = False
                self._writer = None
                async with self._state.lock:
                    self._state.rp2040_connected = False
                if self._config_done_future and not self._config_done_future.done():
                    self._config_done_future.set_result(False)
                if self._reset_future and not self._reset_future.done():
                    self._reset_future.set_result(False)
                if self._measure_pulse_future and not self._measure_pulse_future.done():
                    self._measure_pulse_future.set_result(None)
                await asyncio.sleep(RECONNECT_DELAY)

    async def _connect_and_run(self):
        log.info(f"Connecting to RP2040 at {SERIAL_PORT} ({SERIAL_BAUD} baud)")
        reader, writer = await serial_asyncio.open_serial_connection(
            url=SERIAL_PORT, baudrate=SERIAL_BAUD
        )
        self._writer = writer
        self._connected = True
        async with self._state.lock:
            self._state.rp2040_connected = True
        log.info("RP2040 connected")

        await self._send_raw(proto.cmd_set_rate(STREAM_HZ))

        await asyncio.gather(
            self._read_loop(reader),
            self._write_loop(),
        )

    async def _read_loop(self, reader: asyncio.StreamReader):
        while True:
            chunk = await reader.read(256)
            if not chunk:
                raise ConnectionResetError("Serial port closed")
            packets = self._parser.feed(chunk)
            for pkt in packets:
                await self._handle_packet(pkt)

    async def _write_loop(self):
        while True:
            try:
                data = await asyncio.wait_for(self._cmd_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                # No command in 100 ms — send a heartbeat to keep the watchdog fed.
                if not self._connected:
                    continue
                data = proto.cmd_heartbeat()
            if self._writer:
                self._writer.write(data)
                await self._writer.drain()

    async def _send_raw(self, data: bytes):
        if self._writer:
            self._writer.write(data)
            await self._writer.drain()

    async def _handle_packet(self, pkt: dict):
        ptype = pkt.get("type")

        if ptype == "state":
            async with self._state.lock:
                self._state.rp2040_ts = pkt["ts"]
                for port_id, pdata in pkt["ports"].items():
                    existing = self._state.ports.get(port_id, {})
                    existing.update(pdata)
                    self._state.ports[port_id] = existing

        elif ptype == "uart_rx":
            async with self._state.lock:
                port_id = pkt.get("port", 15)
                buf = self._state.uart_rx_buffers.get(port_id)
                if buf is not None:
                    buf.extend(pkt["data"])

        elif ptype == "ack":
            cmd = pkt.get("cmd")
            if cmd == proto.CMD_CONFIG_DONE:
                if self._config_done_future and not self._config_done_future.done():
                    self._config_done_future.set_result(True)
            elif cmd == proto.CMD_RESET:
                if self._reset_future and not self._reset_future.done():
                    self._reset_future.set_result(True)

        elif ptype == "measure_pulse":
            pulse_us = pkt.get("pulse_us", 0)
            if self._measure_pulse_future and not self._measure_pulse_future.done():
                self._measure_pulse_future.set_result(pulse_us)

        elif ptype == "error":
            code = pkt.get("code", 0)
            msg  = pkt.get("message", "")
            log.error(f"RP2040 error 0x{code:02X}: {msg}")
            async with self._state.lock:
                self._state.add_log("error", f"[RP2040] {msg}")
            # Only a PWM slice conflict during CONFIG_DONE should abort finalize.
            # Unrelated errors (ERR_CONFIG_LOCKED, ERR_BAD_TYPE, etc.) must not be
            # misreported as PWM conflicts — those are logged above and ignored here.
            if code == proto.ERR_PORT_CONFLICT:
                if self._config_done_future and not self._config_done_future.done():
                    self._config_done_future.set_result(False)
            if self._reset_future and not self._reset_future.done():
                self._reset_future.set_result(False)
            if self._measure_pulse_future and not self._measure_pulse_future.done():
                self._measure_pulse_future.set_result(None)

    # ------------------------------------------------------------------
    # Public command API
    # ------------------------------------------------------------------

    def enqueue(self, data: bytes):
        try:
            self._cmd_queue.put_nowait(data)
        except asyncio.QueueFull:
            log.warning("RP2040 command queue full — dropping command")

    async def configure_port(self, port_id: int, port_type_str: str, baud: int = 0) -> bool:
        type_id = proto.PORT_TYPE_IDS.get(port_type_str)
        if type_id is None:
            return False
        if type_id == proto.PORT_UART:
            self.enqueue(proto.cmd_configure_uart(port_id, baud or 115200))
        else:
            self.enqueue(proto.cmd_configure(port_id, type_id))
            if type_id == proto.PORT_MOTOR_SERVO:
                # RC ESC protocol: 1500µs stop, 1100µs full reverse, 1900µs full forward.
                self.enqueue(proto.cmd_set_servo_range(port_id, 1100, 1900))
        return True

    async def finalize_config(self, timeout: float = 2.0):
        """Send CMD_CONFIG_DONE and wait for ACK or ERROR.

        Returns True on success, False on conflict, or raises asyncio.TimeoutError
        if the RP2040 does not respond within *timeout* seconds.
        """
        loop = asyncio.get_running_loop()
        self._config_done_future = loop.create_future()
        self.enqueue(proto.cmd_config_done())
        try:
            return await asyncio.wait_for(
                asyncio.shield(self._config_done_future), timeout=timeout
            )
        except asyncio.TimeoutError:
            log.warning("CONFIG_DONE timed out — RP2040 may not be connected")
            raise
        finally:
            self._config_done_future = None

    async def reset(self, timeout: float = 2.0) -> bool:
        """Send CMD_RESET and wait for ACK. Returns True on success."""
        loop = asyncio.get_running_loop()
        self._reset_future = loop.create_future()
        self.enqueue(proto.cmd_reset())
        try:
            return await asyncio.wait_for(
                asyncio.shield(self._reset_future), timeout=timeout
            )
        except asyncio.TimeoutError:
            log.warning("CMD_RESET timed out — RP2040 may not be connected yet")
            return False
        finally:
            self._reset_future = None

    async def measure_pulse(self, port_id: int, timeout: float = 3.0) -> int | None:
        """Send CMD_MEASURE_PULSE and wait for RESP_MEASURE_PULSE.

        Returns measured pulse width in µs, or None on timeout or firmware error.
        The firmware blocks for up to 150 ms waiting for a pulse — only call during calibration.
        """
        loop = asyncio.get_running_loop()
        self._measure_pulse_future = loop.create_future()
        self.enqueue(proto.cmd_measure_pulse(port_id))
        try:
            return await asyncio.wait_for(
                asyncio.shield(self._measure_pulse_future), timeout=timeout
            )
        except asyncio.TimeoutError:
            log.warning("CMD_MEASURE_PULSE timed out")
            return None
        finally:
            self._measure_pulse_future = None

    def stop_all(self):
        self.enqueue(proto.cmd_stop_all())

    @property
    def connected(self) -> bool:
        return self._connected
