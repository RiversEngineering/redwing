"""FastAPI web application — dashboard WebSocket, MJPEG stream, REST."""

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .camera import CameraCapture
from .config import STREAM_HZ
from .state import SharedState

log = logging.getLogger(__name__)

BOUNDARY = b"--frame"
MJPEG_CONTENT_TYPE = "multipart/x-mixed-replace; boundary=frame"


def create_app(state: SharedState, camera: CameraCapture) -> FastAPI:
    app = FastAPI(title="Redwing Dashboard")

    ws_clients: set[WebSocket] = set()
    log_clients: set[WebSocket] = set()

    # ------------------------------------------------------------------
    # WebSocket — real-time state stream to dashboard
    # ------------------------------------------------------------------

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        ws_clients.add(ws)
        log.info(f"Dashboard connected: {ws.client}")
        try:
            while True:
                # Send a keepalive ping — actual state is pushed by the broadcast task
                await asyncio.sleep(30)
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
                ws_clients -= dead
            await asyncio.sleep(interval)

    async def _broadcast_logs():
        """Tail new log entries and push to all dashboard clients."""
        sent_count = 0
        while True:
            async with state.lock:
                new_entries = state.logs[sent_count:]
                sent_count = len(state.logs)

            if new_entries and ws_clients:
                dead = set()
                for ws in list(ws_clients):
                    for entry in new_entries:
                        try:
                            await ws.send_json(entry)
                        except Exception:
                            dead.add(ws)
                            break
                ws_clients -= dead

            await asyncio.sleep(0.1)

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
                    b"Content-Type: image/jpeg\r\n\r\n"
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
