"""Redwing daemon — main entry point.

Starts all subsystems and runs them concurrently:
  - RP2040 serial communication
  - ZeroMQ IPC server (student library bridge)
  - Camera capture
  - FastAPI web server (dashboard + MJPEG)

Usage:
    python -m daemon.main
    # or via Docker:
    python -m daemon.main --serial /dev/ttyACM0
"""

import asyncio
import logging
import os
import signal
import sys

import uvicorn

from .api import create_app
from .camera import CameraCapture
from .config import WEB_HOST, WEB_PORT, SERIAL_PORT, LIDAR_PORT
from .ipc import IPCServer
from .lidar import LidarCapture
from .rp2040 import RP2040
from .state import SharedState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("redwing.daemon")


async def main():
    log.info("=== Redwing Daemon Starting ===")
    log.info(f"Serial: {SERIAL_PORT}  Web: {WEB_HOST}:{WEB_PORT}")
    if LIDAR_PORT:
        log.info(f"LIDAR: {LIDAR_PORT}")

    state  = SharedState()
    rp     = RP2040(state)
    camera = CameraCapture(state)
    ipc    = IPCServer(state, rp)
    app    = create_app(state, camera)

    config = uvicorn.Config(
        app,
        host=WEB_HOST,
        port=WEB_PORT,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown(server, rp)))

    tasks = [rp.run(), ipc.run(), camera.run(), server.serve()]
    if LIDAR_PORT:
        tasks.append(LidarCapture(state, LIDAR_PORT).run())

    await asyncio.gather(*tasks)


async def _shutdown(server: uvicorn.Server, rp: RP2040):
    log.info("Shutting down...")
    rp.stop_all()
    server.should_exit = True


if __name__ == "__main__":
    asyncio.run(main())
