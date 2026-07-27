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
        self._pca = None   # set by main.py via set_pca()

    def set_pca(self, pca) -> None:
        self._pca = pca
        self._ctx = zmq.asyncio.Context()

        self._pub  = self._ctx.socket(zmq.PUB)
        self._pull = self._ctx.socket(zmq.PULL)
        self._pull.setsockopt(zmq.RCVHWM, 20)  # match library SNDHWM
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
                uart_rx_deltas = self._state.get_uart_rx_deltas()
            if uart_rx_deltas:
                msg["uart_rx"] = {
                    str(pid): base64.b64encode(data).decode()
                    for pid, data in uart_rx_deltas.items()
                }
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

        elif c == "set_position":
            port         = cmd["port"]
            target       = int(cmd["target"])
            speed_limit  = int(cmd.get("speed_limit", 0))
            keep         = bool(cmd.get("keep_integral", False))
            self._rp.enqueue(proto.cmd_set_position(port, target, speed_limit, keep))

        elif c == "invert_encoder":
            port = cmd["port"]
            inverted = bool(cmd.get("inverted", False))
            self._rp.enqueue(proto.cmd_invert_encoder(port, inverted))
            async with self._state.lock:
                self._state.ports.setdefault(str(port), {})["inverted"] = inverted
                self._state.port_invert[str(port)] = inverted
                self._state.port_invert_code_set.add(str(port))

        elif c == "set_pos_options":
            self._rp.enqueue(proto.cmd_set_pos_options(
                cmd["port"],
                float(cmd.get("deadband",        0.0)),
                float(cmd.get("output_floor",    0.0)),
                float(cmd.get("ramp_rate",       0.0)),
                float(cmd.get("d_alpha",         1.0)),
                float(cmd.get("approach_factor", 0.0)),
            ))

        elif c == "set_pid":
            self._rp.enqueue(
                proto.cmd_set_pid(cmd["port"], cmd["kp"], cmd["ki"], cmd["kd"],
                                  float(cmd.get("integral_max", 0)))
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
            port    = int(cmd["port"])
            min_us  = int(cmd["min_us"])
            max_us  = int(cmd["max_us"])
            min_a   = float(cmd.get("min_angle", 0.0))
            max_a   = float(cmd.get("max_angle", 300.0))
            async with self._state.lock:
                pd = self._state.ports.setdefault(str(port), {})
                pd["min_angle"]    = min_a
                pd["max_angle"]    = max_a
                pd["min_pulse_us"] = min_us
                pd["max_pulse_us"] = max_us

        elif c == "gobilda_set_mode":
            port = int(cmd["port"])
            mode = 1 if str(cmd.get("mode", "positional")) == "continuous" else 0
            self._rp.enqueue(proto.cmd_gobilda_mode(port, mode))
            async with self._state.lock:
                pd = self._state.ports.setdefault(str(port), {})
                pd["gobilda_mode"] = "continuous" if mode == 1 else "positional"
                if mode == 1:
                    pd["min_angle"] = -100.0; pd["max_angle"] = 100.0
                    pd["min_pulse_us"] = 900; pd["max_pulse_us"] = 2100
                else:
                    pd["min_angle"] = 0.0; pd["max_angle"] = 300.0
                    pd["min_pulse_us"] = 500; pd["max_pulse_us"] = 2500

        elif c == "set_pca_servo_range":
            ch      = int(cmd["channel"])
            min_us  = int(cmd["min_us"])
            max_us  = int(cmd["max_us"])
            min_a   = float(cmd.get("min_angle", 0.0))
            max_a   = float(cmd.get("max_angle", 300.0))
            async with self._state.lock:
                cd = self._state.pca9685_channels.setdefault(ch, {})
                cd["min_angle"]    = min_a
                cd["max_angle"]    = max_a
                cd["min_pulse_us"] = min_us
                cd["max_pulse_us"] = max_us

        elif c == "uart_tx":
            port = int(cmd.get("port", 15))
            data = base64.b64decode(cmd.get("data", ""))
            if data:
                self._rp.enqueue(proto.cmd_uart_tx(port, data))

        elif c == "stop_all":
            self._rp.stop_all()

        elif c == "set_lidar_config":
            async with self._state.lock:
                self._state.lidar_offset_deg      = float(cmd.get("offset", 0.0)) % 360.0
                self._state.lidar_x_offset_cm     = float(cmd.get("x_offset", 0.0))
                self._state.lidar_y_offset_cm     = float(cmd.get("y_offset", 0.0))
                if "max_cm" in cmd:
                    self._state.lidar_max_cm      = max(50.0, min(2000.0, float(cmd["max_cm"])))
                self._state.lidar_code_configured = True

        elif c == "set_imu_mount":
            async with self._state.lock:
                self._state.imu_mount_yaw      = float(cmd.get("yaw",   0.0))
                self._state.imu_mount_pitch    = float(cmd.get("pitch", 0.0))
                self._state.imu_mount_roll     = float(cmd.get("roll",  0.0))
                self._state.imu_mount_code_set = True

        elif c == "set_motor_invert":
            port = str(cmd.get("port", ""))
            async with self._state.lock:
                self._state.port_invert[port] = bool(cmd.get("inverted", False))
                self._state.port_invert_code_set.add(port)

        elif c == "map_point":
            async with self._state.lock:
                self._state.map_points_buf.append((float(cmd.get("x", 0)), float(cmd.get("y", 0))))
                self._state._map_total_count += 1
                if len(self._state.map_points_buf) > self._state._max_map_buf:
                    self._state.map_points_buf = self._state.map_points_buf[-self._state._max_map_buf:]

        elif c == "map_points":
            pts = cmd.get("points", [])
            async with self._state.lock:
                for pt in pts:
                    if len(pt) >= 2:
                        self._state.map_points_buf.append((float(pt[0]), float(pt[1])))
                        self._state._map_total_count += 1
                if len(self._state.map_points_buf) > self._state._max_map_buf:
                    self._state.map_points_buf = self._state.map_points_buf[-self._state._max_map_buf:]

        elif c == "map_pose":
            async with self._state.lock:
                self._state.map_pose = {
                    "x":       float(cmd.get("x", 0)),
                    "y":       float(cmd.get("y", 0)),
                    "heading": float(cmd.get("heading", 0)),
                }

        elif c == "clear_map":
            async with self._state.lock:
                self._state.clear_map()

        elif c == "plot":
            label = str(cmd.get("label", ""))[:64]
            value = float(cmd.get("value", 0.0))
            if label:
                async with self._state.lock:
                    self._state.add_plot(label, value)

        elif c == "pca_set_motor":
            channel = int(cmd["channel"])
            val_x100 = int(cmd["value"])   # -10000..+10000 (same scale as RP2040 motors)
            if self._pca and self._pca.present:
                # RC ESC: 1500 µs stop, 1100 µs full reverse, 1900 µs full forward
                pulse_us = 1500 + (val_x100 * 400) // 10000
                self._pca.set_channel_pulse_us(channel, pulse_us)
                async with self._state.lock:
                    self._state.pca9685_channels.setdefault(channel, {})["pulse_us"] = pulse_us

        elif c == "pca_set_servo":
            channel  = int(cmd["channel"])
            pulse_us = int(cmd["pulse_us"])
            if self._pca and self._pca.present:
                self._pca.set_channel_pulse_us(channel, pulse_us)
                async with self._state.lock:
                    self._state.pca9685_channels.setdefault(channel, {})["pulse_us"] = pulse_us

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
        if cmd == "pca_configure":
            return await self._do_pca_configure(req)
        if cmd == "pca_calibrate":
            return await self._do_pca_calibrate(req)
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
            if port_type in ("uart", "tfluna", "tfmini") and port_id not in (14, 15):
                return {"ok": False, "error": "UART / TF-Luna / TF-Mini is only available on D6 (port 14) or D7 (port 15)."}
            if port_type == "ir_distance" and port_id not in (5, 6, 7):
                return {"ok": False, "error": "IR distance sensor is only available on S5, S6, or S7 (ADC-capable ports)."}

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

    async def _do_pca_configure(self, req: dict) -> dict:
        channel   = int(req.get("channel", -1))
        port_type = str(req.get("type", ""))
        if channel < 0 or channel > 15:
            return {"ok": False, "error": f"Invalid PCA channel {channel}. Must be 0–15."}
        if port_type not in ("motor_servo_signal", "servo"):
            return {"ok": False, "error": f"PCA9685 only supports 'motor_servo_signal' and 'servo', got {port_type!r}"}
        if not self._pca or not self._pca.present:
            return {"ok": False, "error": "PCA9685 not detected"}
        self._pca.configure_channel(channel, port_type)
        async with self._state.lock:
            self._state.pca9685_channels[channel] = {"type": port_type, "pulse_us": 1500}
        return {"ok": True}

    async def _do_pca_calibrate(self, req: dict) -> dict:
        pico_port = int(req.get("pico_port", -1))
        if pico_port < 0 or pico_port > 7:
            return {"ok": False, "error": f"pico_port must be a single-pin port 0–7 (S0–S7), got {pico_port}"}
        if not self._pca or not self._pca.present:
            return {"ok": False, "error": "PCA9685 not detected"}
        result = await self._pca.calibrate(pico_port)
        async with self._state.lock:
            self._state.pca9685_last_calibration = result
        return result

    async def _do_reset(self) -> dict:
        ok = await self._rp.reset()
        async with self._state.lock:
            self._state.config_finalized = False
            self._state.port_config.clear()
            self._state.ports.clear()
            self._state.logs.clear()
            self._state.lidar_code_configured = False   # dashboard regains control on new run
            self._state.imu_mount_code_set    = False
            self._state.port_invert_code_set.clear()
        if not ok:
            log.warning("CMD_RESET timed out — RP2040 may not be connected yet")
        return {"ok": True}   # best-effort: always let the student program continue
