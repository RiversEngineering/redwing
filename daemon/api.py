"""FastAPI web application — dashboard WebSocket, MJPEG stream, REST."""

import asyncio
import base64
import logging
from typing import AsyncIterator, TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .camera import CameraCapture
from .config import STREAM_HZ
from .state import SharedState
from . import protocol as proto

if TYPE_CHECKING:
    from .rp2040 import RP2040

log = logging.getLogger(__name__)

BOUNDARY = b"--frame"
MJPEG_CONTENT_TYPE = "multipart/x-mixed-replace; boundary=frame"


def create_app(state: SharedState, camera: CameraCapture, rp: "RP2040") -> FastAPI:
    app = FastAPI(title="Redwing Dashboard")

    ws_clients: set[WebSocket] = set()
    log_clients: set[WebSocket] = set()

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
                # angle_deg 0..300 → pulse_us 500..2500 µs (default 300° servo range)
                angle = max(0.0, min(300.0, float(msg.get("angle_deg", 150))))
                pulse_us = int(500 + angle / 300.0 * 2000)
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
    import os
    dashboard_dir = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")
    if os.path.isdir(dashboard_dir):
        app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
    else:
        @app.get("/")
        async def root():
            return {"message": "Redwing daemon running. Dashboard not built yet."}

    return app
