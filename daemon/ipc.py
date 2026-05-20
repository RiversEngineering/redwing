"""ZeroMQ IPC server — bridges student library processes and the daemon.

Sockets:
  PUB  5555  — broadcasts state JSON to all subscriber libraries
  PULL 5556  — receives fire-and-forget commands from library PUSH sockets
  REP  5557  — handles synchronous config requests (port setup)

Config finalization:
  Once all ports are configured, the first runtime command (set_motor, etc.)
  triggers CMD_CONFIG_DONE, which tells the RP2040 to validate PWM slice
  conflicts and lock the configuration.  Subsequent configure attempts are
  rejected by the firmware.
"""

import asyncio
import base64
import logging

import zmq
import zmq.asyncio

from . import protocol as proto
from .config import ZMQ_PUB_PORT, ZMQ_PULL_PORT, ZMQ_REP_PORT, STREAM_HZ
from .state import SharedState
from .rp2040 import RP2040

log = logging.getLogger(__name__)


class IPCServer:
    def __init__(self, state: SharedState, rp: RP2040):
        self._state = state
        self._rp = rp
        self._ctx = zmq.asyncio.Context()

        self._pub  = self._ctx.socket(zmq.PUB)
        self._pull = self._ctx.socket(zmq.PULL)
        self._rep  = self._ctx.socket(zmq.REP)

        self._pub.bind(f"tcp://*:{ZMQ_PUB_PORT}")
        self._pull.bind(f"tcp://*:{ZMQ_PULL_PORT}")
        self._rep.bind(f"tcp://*:{ZMQ_REP_PORT}")

        log.info(
            f"ZeroMQ: PUB={ZMQ_PUB_PORT}, PULL={ZMQ_PULL_PORT}, REP={ZMQ_REP_PORT}"
        )

    async def run(self):
        await asyncio.gather(
            self._publish_loop(),
            self._command_loop(),
            self._config_loop(),
        )

    async def _publish_loop(self):
        interval = 1.0 / STREAM_HZ
        while True:
            async with self._state.lock:
                msg = self._state.to_ws_message()
                uart_rx = self._state.get_uart_rx_delta()
            if uart_rx:
                msg["uart_rx"] = base64.b64encode(uart_rx).decode()
            self._pub.send_json(msg, zmq.NOBLOCK)
            await asyncio.sleep(interval)

    async def _command_loop(self):
        while True:
            try:
                cmd = await self._pull.recv_json()
                await self._dispatch_command(cmd)
            except Exception as e:
                log.error(f"IPC command error: {e}")

    async def _config_loop(self):
        while True:
            try:
                req = await self._rep.recv_json()
                reply = await self._handle_config(req)
                await self._rep.send_json(reply)
            except Exception as e:
                log.error(f"IPC config error: {e}")
                await self._rep.send_json({"ok": False, "error": str(e)})

    async def _dispatch_command(self, cmd: dict):
        c = cmd.get("cmd")

        if c == "set_motor":
            port = cmd["port"]
            val  = int(cmd["value"])
            self._rp.enqueue(proto.cmd_set_motor(port, val))

        elif c == "set_servo":
            self._rp.enqueue(proto.cmd_set_servo(cmd["port"], int(cmd["pulse_us"])))

        elif c == "set_velocity":
            port = cmd["port"]
            vel_x10 = int(float(cmd["velocity"]) * 10)
            self._rp.enqueue(proto.cmd_set_velocity(port, vel_x10))
            async with self._state.lock:
                self._state.target_velocities[port] = float(cmd["velocity"])
                self._state.ports.setdefault(str(port), {})["target_velocity"] = float(cmd["velocity"])

        elif c == "set_pid":
            self._rp.enqueue(
                proto.cmd_set_pid(cmd["port"], cmd["kp"], cmd["ki"], cmd["kd"])
            )

        elif c == "reset_encoder":
            self._rp.enqueue(proto.cmd_reset_encoder(cmd["port"]))

        elif c == "set_gpio":
            self._rp.enqueue(proto.cmd_set_gpio(cmd["port"], int(cmd["state"])))

        elif c == "attach_encoder":
            m_port = cmd["motor_port"]
            e_port = cmd["encoder_port"]
            self._rp.enqueue(proto.cmd_attach_encoder(m_port, e_port))
            async with self._state.lock:
                self._state.encoder_map[m_port] = e_port

        elif c == "set_servo_range":
            self._rp.enqueue(
                proto.cmd_set_servo_range(cmd["port"], cmd["min_us"], cmd["max_us"])
            )

        elif c == "uart_tx":
            data = base64.b64decode(cmd.get("data", ""))
            if data:
                self._rp.enqueue(proto.cmd_uart_tx(data))

        elif c == "stop_all":
            self._rp.stop_all()

        elif c == "log":
            level   = cmd.get("level", "info")
            message = cmd.get("message", "")
            async with self._state.lock:
                self._state.add_log(level, message)
            log.debug(f"[student log] {level}: {message}")

        elif c == "camera_show_raw":
            async with self._state.lock:
                self._state.show_raw = True

        elif c == "camera_show_frame":
            frame_b64 = cmd.get("frame", "")
            frame_bytes = base64.b64decode(frame_b64) if frame_b64 else None
            async with self._state.lock:
                self._state.camera_override = frame_bytes
                self._state.show_raw = False

        else:
            log.warning(f"Unknown IPC command: {c!r}")

    async def _handle_config(self, req: dict) -> dict:
        cmd = req.get("cmd")
        if cmd == "configure":
            return await self._do_configure(req)
        if cmd == "finalize":
            return await self._do_finalize()
        if cmd == "reset":
            return await self._do_reset()
        return {"ok": False, "error": f"Unknown config request: {cmd!r}"}

    async def _do_configure(self, req: dict) -> dict:
        port_id   = int(req["port"])
        port_type = str(req["type"])
        baud      = int(req.get("baud", 0))

        if port_type not in proto.PORT_TYPE_IDS:
            return {"ok": False, "error": f"Unknown port type '{port_type}'"}

        async with self._state.lock:
            if self._state.config_finalized:
                return {
                    "ok": False,
                    "error": (
                        "Cannot configure ports after robot.start(). "
                        "Move all device setup calls above robot.start()."
                    ),
                }
            if str(port_id) in self._state.port_config:
                existing = self._state.port_config[str(port_id)]
                return {
                    "ok": False,
                    "error": (
                        f"Port {port_id} is already configured as {existing}. "
                        "Each port can only be configured once."
                    ),
                }
            if port_type == "uart" and port_id != 15:
                return {"ok": False, "error": "UART is only available on D7 (port 15)."}

        ok = await self._rp.configure_port(port_id, port_type, baud)
        if ok:
            async with self._state.lock:
                self._state.port_config[str(port_id)] = port_type
                self._state.ports.setdefault(str(port_id), {})["type"] = port_type

        return {"ok": ok, "error": "" if ok else "RP2040 did not accept configuration"}

    async def _do_finalize(self) -> dict:
        async with self._state.lock:
            if self._state.config_finalized:
                return {"ok": True}
        try:
            ok = await self._rp.finalize_config()
        except asyncio.TimeoutError:
            log.warning("finalize_config timed out — RP2040 not responding")
            async with self._state.lock:
                self._state.add_log(
                    "warning",
                    "[Daemon] RP2040 did not respond to CMD_CONFIG_DONE — "
                    "check serial connection.",
                )
            return {"ok": False, "error": "RP2040 not responding"}
        if ok:
            async with self._state.lock:
                self._state.config_finalized = True
        else:
            log.error("RP2040 rejected configuration — PWM slice conflict (see dashboard log).")
        return {"ok": ok, "error": "" if ok else "RP2040 rejected configuration"}

    async def _do_reset(self) -> dict:
        ok = await self._rp.reset()
        async with self._state.lock:
            self._state.config_finalized = False
            self._state.port_config.clear()
            self._state.ports.clear()
            self._state.logs.clear()
        if not ok:
            log.warning("CMD_RESET timed out — RP2040 may not be connected yet")
        return {"ok": True}   # best-effort: always let the student program continue
