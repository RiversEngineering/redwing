"""FastAPI web application — dashboard WebSocket, MJPEG stream, REST."""

import asyncio
import base64
import logging
import os
from typing import AsyncIterator, TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .camera import CameraCapture
from .config import STREAM_HZ, FIRMWARE_UF2_PATH
from .state import SharedState
from . import protocol as proto

if TYPE_CHECKING:
    from .rp2040 import RP2040

log = logging.getLogger(__name__)

BOUNDARY = b"--frame"
MJPEG_CONTENT_TYPE = "multipart/x-mixed-replace; boundary=frame"


def create_app(state: SharedState, camera: CameraCapture, rp: "RP2040", pca=None) -> FastAPI:
    app = FastAPI(title="Redwing Dashboard")

    ws_clients: set[WebSocket] = set()
    log_clients: set[WebSocket] = set()
    flash_state = {"running": False}

    # ------------------------------------------------------------------
    # WebSocket — real-time state stream + dashboard command receiver
    # ------------------------------------------------------------------

    async def _handle_ws_command(msg: dict) -> None:
        """Route a JSON command received from the dashboard to the RP2040."""
        cmd = msg.get("cmd")
        try:
            if cmd == "set_motor":
                port = int(msg["port"])
                # value_pct is -100.0..+100.0 → RP2040 expects -10000..+10000
                value = int(max(-10000, min(10000, float(msg.get("value_pct", 0)) * 100)))
                rp.enqueue(proto.cmd_set_motor(port, value))

            elif cmd == "set_servo":
                port = int(msg["port"])
                async with state.lock:
                    pd = state.ports.get(str(port), {})
                    min_a  = pd.get("min_angle",    0.0)
                    max_a  = pd.get("max_angle",  300.0)
                    min_us = pd.get("min_pulse_us", 500)
                    max_us = pd.get("max_pulse_us", 2500)
                lo, hi = (min_a, max_a) if min_a <= max_a else (max_a, min_a)
                angle = max(lo, min(hi, float(msg.get("angle_deg", (min_a + max_a) / 2))))
                t = (angle - min_a) / (max_a - min_a) if max_a != min_a else 0.5
                pulse_us = int(min_us + t * (max_us - min_us))
                rp.enqueue(proto.cmd_set_servo(port, pulse_us))

            elif cmd == "set_gpio":
                port = int(msg["port"])
                rp.enqueue(proto.cmd_set_gpio(port, 1 if msg.get("state") else 0))

            elif cmd == "reset_encoder":
                port = int(msg["port"])
                rp.enqueue(proto.cmd_reset_encoder(port))

            elif cmd == "stop_all":
                rp.enqueue(proto.cmd_stop_all())

            elif cmd == "configure_port":
                port = int(msg["port"])
                port_type = str(msg["type"])
                if port_type not in proto.PORT_TYPE_IDS:
                    async with state.lock:
                        state.add_log("error", f"[Dashboard] Unknown port type: {port_type!r}")
                    return
                if port_type == "ir_distance" and port not in (5, 6, 7):
                    async with state.lock:
                        state.add_log("error", "[Dashboard] IR distance sensor requires S5, S6, or S7 (ADC-capable ports only).")
                    return
                async with state.lock:
                    if state.config_finalized:
                        state.add_log("warning", "[Dashboard] Cannot configure: student code locked the configuration. Reset ports first.")
                        return
                ok = await rp.configure_port(port, port_type)
                async with state.lock:
                    if ok:
                        state.port_config[str(port)] = port_type
                        state.ports.setdefault(str(port), {})["type"] = port_type
                        state.add_log("info", f"[Dashboard] P{port} configured as {port_type}")
                    else:
                        state.add_log("error", f"[Dashboard] Failed to configure P{port} as {port_type}")

            elif cmd == "reset_ports":
                ok = await rp.reset()
                async with state.lock:
                    state.config_finalized = False
                    state.port_config.clear()
                    state.ports.clear()
                    state.add_log("info", "[Dashboard] All ports reset")

            elif cmd == "system_power":
                action = msg.get("action")  # "shutdown" or "reboot"
                if action in ("shutdown", "reboot"):
                    log.warning(f"System {action} requested from dashboard")
                    asyncio.create_task(_do_power(action, ws_clients))

            elif cmd == "flash_firmware":
                if flash_state["running"]:
                    async with state.lock:
                        state.add_log("warning", "[Dashboard] Firmware flash already in progress")
                else:
                    log.warning("Firmware flash requested from dashboard")
                    asyncio.create_task(_do_flash_firmware(ws_clients))

            elif cmd == "clear_map":
                async with state.lock:
                    state.clear_map()
                # Broadcast so every connected dashboard clears its local accumulation
                dead = set()
                for ws in list(ws_clients):
                    try:
                        await ws.send_json({"type": "clear_map"})
                    except Exception:
                        dead.add(ws)
                ws_clients.difference_update(dead)

            elif cmd == "pca_configure":
                channel   = int(msg["channel"])
                port_type = str(msg["type"])
                if port_type not in ("motor_servo_signal", "servo"):
                    async with state.lock:
                        state.add_log("error", f"[Dashboard] PCA channel type must be motor_servo_signal or servo")
                    return
                if not pca or not pca.present:
                    async with state.lock:
                        state.add_log("warning", "[Dashboard] PCA9685 not detected")
                    return
                pca.configure_channel(channel, port_type)
                async with state.lock:
                    state.pca9685_channels[channel] = {"type": port_type, "pulse_us": 1500}
                    state.add_log("info", f"[Dashboard] PCA P{channel} configured as {port_type}")

            elif cmd == "pca_set_motor":
                channel  = int(msg["channel"])
                val_x100 = int(max(-10000, min(10000, float(msg.get("value_pct", 0)) * 100)))
                if pca and pca.present:
                    pulse_us = 1500 + (val_x100 * 400) // 10000
                    pca.set_channel_pulse_us(channel, pulse_us)
                    async with state.lock:
                        state.pca9685_channels.setdefault(channel, {})["pulse_us"] = pulse_us

            elif cmd == "set_servo_range":
                port   = int(msg["port"])
                min_a  = float(msg.get("min_angle",    0.0))
                max_a  = float(msg.get("max_angle",  300.0))
                min_us = int(msg.get("min_pulse_us",   500))
                max_us = int(msg.get("max_pulse_us",  2500))
                async with state.lock:
                    pd = state.ports.setdefault(str(port), {})
                    pd["min_angle"]    = min_a
                    pd["max_angle"]    = max_a
                    pd["min_pulse_us"] = min_us
                    pd["max_pulse_us"] = max_us

            elif cmd == "gobilda_set_mode":
                port = int(msg["port"])
                mode = 1 if str(msg.get("mode", "positional")) == "continuous" else 0
                rp.enqueue(proto.cmd_gobilda_mode(port, mode))
                async with state.lock:
                    pd = state.ports.setdefault(str(port), {})
                    pd["gobilda_mode"] = "continuous" if mode == 1 else "positional"
                    if mode == 1:
                        pd["min_angle"] = -100.0; pd["max_angle"] = 100.0
                        pd["min_pulse_us"] = 900; pd["max_pulse_us"] = 2100
                    else:
                        pd["min_angle"] = 0.0; pd["max_angle"] = 300.0
                        pd["min_pulse_us"] = 500; pd["max_pulse_us"] = 2500

            elif cmd == "set_pca_servo_range":
                ch     = int(msg["channel"])
                min_a  = float(msg.get("min_angle",    0.0))
                max_a  = float(msg.get("max_angle",  300.0))
                min_us = int(msg.get("min_pulse_us",   500))
                max_us = int(msg.get("max_pulse_us",  2500))
                async with state.lock:
                    cd = state.pca9685_channels.setdefault(ch, {})
                    cd["min_angle"]    = min_a
                    cd["max_angle"]    = max_a
                    cd["min_pulse_us"] = min_us
                    cd["max_pulse_us"] = max_us

            elif cmd == "pca_set_servo":
                channel  = int(msg["channel"])
                async with state.lock:
                    cd = state.pca9685_channels.get(channel, {})
                    min_a  = cd.get("min_angle",    0.0)
                    max_a  = cd.get("max_angle",  300.0)
                    min_us = cd.get("min_pulse_us", 500)
                    max_us = cd.get("max_pulse_us", 2500)
                lo, hi   = (min_a, max_a) if min_a <= max_a else (max_a, min_a)
                angle    = max(lo, min(hi, float(msg.get("angle_deg", (min_a + max_a) / 2))))
                t        = (angle - min_a) / (max_a - min_a) if max_a != min_a else 0.5
                pulse_us = int(min_us + t * (max_us - min_us))
                if pca and pca.present:
                    pca.set_channel_pulse_us(channel, pulse_us)
                    async with state.lock:
                        state.pca9685_channels.setdefault(channel, {})["pulse_us"] = pulse_us

            elif cmd == "pca_calibrate":
                pico_port = int(msg.get("pico_port", 0))
                if pca and pca.present:
                    result = await pca.calibrate(pico_port)
                    async with state.lock:
                        state.pca9685_last_calibration = result
                        if result["ok"]:
                            state.add_log(
                                "info",
                                f"[Dashboard] PCA9685 calibrated: osc={result['osc_freq']} Hz, "
                                f"prescale={result['prescale']}, measured={result['measured_us']} µs"
                            )
                        else:
                            state.add_log("error", f"[Dashboard] PCA calibration failed: {result['error']}")

            elif cmd == "set_lidar_config":
                async with state.lock:
                    # max_cm is a display preference — always user-adjustable
                    if "max_cm" in msg:
                        state.lidar_max_cm = max(50.0, min(2000.0, float(msg["max_cm"])))
                    # offset / xy are physical calibration — locked once code sets them
                    if not state.lidar_code_configured:
                        if "offset" in msg:
                            state.lidar_offset_deg  = float(msg["offset"]) % 360.0
                        if "x_offset" in msg:
                            state.lidar_x_offset_cm = max(-200.0, min(200.0, float(msg["x_offset"])))
                        if "y_offset" in msg:
                            state.lidar_y_offset_cm = max(-200.0, min(200.0, float(msg["y_offset"])))

            elif cmd == "set_imu_mount":
                async with state.lock:
                    if not state.imu_mount_code_set:
                        if "yaw"   in msg: state.imu_mount_yaw   = float(msg["yaw"])
                        if "pitch" in msg: state.imu_mount_pitch = float(msg["pitch"])
                        if "roll"  in msg: state.imu_mount_roll  = float(msg["roll"])

            elif cmd == "set_port_invert":
                port = str(msg.get("port", ""))
                async with state.lock:
                    if port and port not in state.port_invert_code_set:
                        inv = bool(msg.get("inverted", False))
                        state.port_invert[port] = inv
                        # Encoders: propagate direction change to firmware
                        if state.ports.get(port, {}).get("type") == "encoder":
                            rp.enqueue(proto.cmd_invert_encoder(int(port), inv))

            elif cmd == "gamepad":
                async with state.lock:
                    gp = state.gamepad
                    gp.lx = max(-1.0, min(1.0, float(msg.get("lx", 0.0))))
                    gp.ly = max(-1.0, min(1.0, float(msg.get("ly", 0.0))))
                    gp.rx = max(-1.0, min(1.0, float(msg.get("rx", 0.0))))
                    gp.ry = max(-1.0, min(1.0, float(msg.get("ry", 0.0))))
                    gp.a     = bool(msg.get("a",     False))
                    gp.b     = bool(msg.get("b",     False))
                    gp.x     = bool(msg.get("x",     False))
                    gp.y     = bool(msg.get("y",     False))
                    gp.up    = bool(msg.get("up",    False))
                    gp.down  = bool(msg.get("down",  False))
                    gp.left  = bool(msg.get("left",  False))
                    gp.right = bool(msg.get("right", False))
                    gp.lb = bool(msg.get("lb", False))
                    gp.rb = bool(msg.get("rb", False))
                    gp.lt = max(0.0, min(1.0, float(msg.get("lt", 0.0))))
                    gp.rt = max(0.0, min(1.0, float(msg.get("rt", 0.0))))
                    gp.connected = True
                    gp.source = "virtual"

            else:
                log.warning(f"Unknown dashboard command: {cmd!r}")
        except (KeyError, ValueError, TypeError) as exc:
            log.warning(f"Malformed dashboard command {msg!r}: {exc}")

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        ws_clients.add(ws)
        log.info(f"Dashboard connected: {ws.client}")
        try:
            while True:
                # Wait up to 30 s for an incoming message (acts as keepalive timeout).
                # Outbound state is pushed by the broadcast tasks in separate coroutines.
                try:
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=30.0)
                    await _handle_ws_command(msg)
                except asyncio.TimeoutError:
                    pass  # No message — connection still alive
        except WebSocketDisconnect:
            pass
        finally:
            ws_clients.discard(ws)
            log.info(f"Dashboard disconnected: {ws.client}")

    # ------------------------------------------------------------------
    # Background task: push state and logs to all WebSocket clients
    # ------------------------------------------------------------------

    @app.on_event("startup")
    async def start_broadcast():
        asyncio.create_task(_broadcast_state())
        asyncio.create_task(_broadcast_logs())
        asyncio.create_task(_broadcast_camera())
        asyncio.create_task(_broadcast_plots())
        asyncio.create_task(_broadcast_map())

    async def _broadcast_state():
        interval = 1.0 / min(STREAM_HZ, 30)  # cap dashboard at 30fps
        while True:
            if ws_clients:
                async with state.lock:
                    msg = state.to_ws_message()
                dead = set()
                for ws in list(ws_clients):
                    try:
                        await ws.send_json(msg)
                    except Exception:
                        dead.add(ws)
                ws_clients.difference_update(dead)
            await asyncio.sleep(interval)

    async def _broadcast_camera():
        """Push camera frames to dashboard clients at ~10 fps via WebSocket."""
        while True:
            if ws_clients:
                jpeg = camera.get_current_jpeg()
                if jpeg:
                    msg = {"type": "frame", "data": base64.b64encode(jpeg).decode()}
                    dead = set()
                    for ws in list(ws_clients):
                        try:
                            await ws.send_json(msg)
                        except Exception:
                            dead.add(ws)
                    ws_clients.difference_update(dead)
            await asyncio.sleep(0.1)  # 10 fps

    async def _broadcast_logs():
        """Tail new log entries and push to all dashboard clients."""
        sent_total = 0  # absolute count of log entries ever sent
        while True:
            async with state.lock:
                total = state._log_total_count
                trimmed = total - len(state.logs)  # entries dropped from front by trim
                idx = max(0, sent_total - trimmed)  # our position in the current list
                new_entries = state.logs[idx:]
                sent_total = total

            if new_entries and ws_clients:
                dead = set()
                for ws in list(ws_clients):
                    for entry in new_entries:
                        try:
                            await ws.send_json(entry)
                        except Exception:
                            dead.add(ws)
                            break
                ws_clients.difference_update(dead)

            await asyncio.sleep(0.1)

    async def _do_power(action: str, clients: set):
        """Notify all clients then shut down or reboot the Pi host."""
        msg = {"type": "system_power", "action": action}
        for ws in list(clients):
            try:
                await ws.send_json(msg)
            except Exception:
                pass
        await asyncio.sleep(1.0)   # give clients time to receive the notification

        import ctypes
        # LINUX_REBOOT_CMD_POWER_OFF = 0x4321FEDC
        # LINUX_REBOOT_CMD_RESTART   = 0x01234567
        magic = 0x4321FEDC if action == "shutdown" else 0x01234567
        ctypes.CDLL("libc.so.6").reboot(ctypes.c_int32(magic))

    async def _broadcast_flash_status(clients: set, flash_status: str, message: str):
        msg = {"type": "flash_status", "state": flash_status, "message": message}
        dead = set()
        for ws in list(clients):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.add(ws)
        clients.difference_update(dead)

    async def _flash_log(level: str, message: str):
        """Log to both the dashboard's WS log stream and `docker compose logs`.

        state.add_log() alone only reaches the dashboard's own Debug Console
        (via the WS broadcast) — it never touches Python's `logging` module,
        so it's invisible to `docker compose logs`. Flashing is exactly the
        kind of thing worth debugging from the container logs alone (no
        browser needed), so mirror every line to both.
        """
        async with state.lock:
            state.add_log(level, message)
        getattr(log, level if level in ("info", "warning", "error") else "info")(message)

    async def _do_flash_firmware(clients: set):
        """Reflash the RP2040 from the on-disk .uf2 via picotool.

        picotool's -f flag resets the Pico into BOOTSEL mode itself (via the
        Pico SDK's USB reset-via-vendor-interface, no physical button press
        needed) before loading, and -x reboots it back into the app once done.
        The daemon's existing serial reconnect loop (rp2040.py) picks the Pico
        back up automatically once it re-enumerates as a CDC device again.
        """
        flash_state["running"] = True
        try:
            await _broadcast_flash_status(clients, "running", "Flashing firmware...")
            await _flash_log("info", "[Dashboard] Flashing firmware...")

            if not os.path.isfile(FIRMWARE_UF2_PATH):
                msg = f"Firmware file not found: {FIRMWARE_UF2_PATH}"
                await _flash_log("error", f"[Dashboard] {msg}")
                await _broadcast_flash_status(clients, "error", msg)
                return

            try:
                proc = await asyncio.create_subprocess_exec(
                    "picotool", "load", "-f", "-x", FIRMWARE_UF2_PATH,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
            except FileNotFoundError:
                msg = "picotool not found — is it installed in the daemon image?"
                await _flash_log("error", f"[Dashboard] {msg}")
                await _broadcast_flash_status(clients, "error", msg)
                return

            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip()
                if text:
                    await _flash_log("info", f"[picotool] {text}")

            rc = await proc.wait()
            if rc == 0:
                await _flash_log("info", "[Dashboard] Firmware flashed successfully")
                await _broadcast_flash_status(clients, "success", "Firmware flashed successfully.")
            else:
                msg = f"picotool exited with code {rc}"
                await _flash_log("error", f"[Dashboard] {msg}")
                await _broadcast_flash_status(clients, "error", msg)
        except Exception as exc:
            log.exception("Firmware flash failed")
            await _flash_log("error", f"[Dashboard] Flash failed: {exc}")
            await _broadcast_flash_status(clients, "error", str(exc))
        finally:
            flash_state["running"] = False

    async def _broadcast_map():
        """Stream new map points to all dashboard clients at ~10 Hz."""
        sent_total = 0
        while True:
            async with state.lock:
                total   = state._map_total_count
                buf     = state.map_points_buf
                trimmed = total - len(buf)
                idx     = max(0, sent_total - trimmed)
                new_pts = buf[idx:]
                sent_total = total

            if new_pts and ws_clients:
                msg  = {"type": "map_points", "points": [[x, y] for x, y in new_pts]}
                dead = set()
                for ws in list(ws_clients):
                    try:
                        await ws.send_json(msg)
                    except Exception:
                        dead.add(ws)
                ws_clients.difference_update(dead)

            await asyncio.sleep(0.1)

    async def _broadcast_plots():
        """Tail new robot.plot() entries and push to all dashboard clients."""
        sent_total = 0
        while True:
            async with state.lock:
                total = state._plot_total_count
                trimmed = total - len(state.plot_points)
                idx = max(0, sent_total - trimmed)
                new_entries = state.plot_points[idx:]
                sent_total = total

            if new_entries and ws_clients:
                dead = set()
                for ws in list(ws_clients):
                    for entry in new_entries:
                        try:
                            await ws.send_json(entry)
                        except Exception:
                            dead.add(ws)
                            break
                ws_clients.difference_update(dead)

            await asyncio.sleep(0.05)  # 20 Hz — fast enough for real-time graphs

    # ------------------------------------------------------------------
    # MJPEG camera stream
    # ------------------------------------------------------------------

    @app.get("/camera")
    async def mjpeg_stream():
        return StreamingResponse(
            _frame_generator(camera),
            media_type=MJPEG_CONTENT_TYPE,
        )

    async def _frame_generator(cam: CameraCapture) -> AsyncIterator[bytes]:
        interval = 1.0 / 30  # stream to browser at up to 30fps
        while True:
            jpeg = cam.get_current_jpeg()
            if jpeg:
                yield (
                    BOUNDARY + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                    + jpeg
                    + b"\r\n"
                )
            await asyncio.sleep(interval)

    # ------------------------------------------------------------------
    # REST — simple health check and state snapshot
    # ------------------------------------------------------------------

    @app.get("/health")
    async def health():
        return {"status": "ok", "uptime": state.uptime}

    @app.get("/state")
    async def get_state():
        async with state.lock:
            return state.to_ws_message()

    # ------------------------------------------------------------------
    # Serve Svelte dashboard static files
    # ------------------------------------------------------------------
    dashboard_dir = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")
    if os.path.isdir(dashboard_dir):
        app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
    else:
        @app.get("/")
        async def root():
            return {"message": "Redwing daemon running. Dashboard not built yet."}

    return app
