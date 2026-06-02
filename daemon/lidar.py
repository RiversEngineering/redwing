"""RPLIDAR driver — reads 360° scans from a USB-connected RPLIDAR A1/A2/S1.

The LIDAR connects directly to the Raspberry Pi via USB (not through the Pico).
Scan data is stored in SharedState.lidar_scan as a list of (angle_deg, distance_cm)
tuples that the student library can read via robot.lidar().

Configuration:
  Set REDWING_LIDAR to the serial port (e.g. /dev/ttyUSB0).
  Leave it empty (the default) to disable LIDAR support.
"""

import asyncio
import logging

from .state import SharedState

log = logging.getLogger(__name__)

_SCAN_QUALITY_MIN = 5   # discard noisy low-quality measurements


class LidarCapture:
    def __init__(self, state: SharedState, port: str):
        self._state = state
        self._port  = port
        self._loop: asyncio.AbstractEventLoop | None = None

    async def run(self):
        self._loop = asyncio.get_running_loop()
        while True:
            try:
                await asyncio.to_thread(self._scan_loop)
            except Exception as e:
                log.warning(f"LIDAR disconnected ({e}). Reconnecting in 3 s...")
                await asyncio.sleep(3)

    def _scan_loop(self):
        try:
            from rplidar import RPLidar, RPLidarException
        except ImportError:
            log.error(
                "rplidar package not installed. "
                "Install it with: pip install rplidar-roboticia"
            )
            return

        lidar = RPLidar(self._port)
        log.info(f"LIDAR connected on {self._port}")
        try:
            # Build scans manually from iter_measures (new_scan, quality, angle, dist_mm)
            scan_buf: list = []
            for new_scan, quality, angle, dist in lidar.iter_measures():
                if new_scan and len(scan_buf) >= 72:
                    points = [
                        (round(a, 1), round(d / 10.0, 1))
                        for q, a, d in scan_buf
                        if q >= _SCAN_QUALITY_MIN and d > 0
                    ]
                    asyncio.run_coroutine_threadsafe(
                        self._update(points), self._loop
                    ).result(timeout=2.0)
                    scan_buf = []
                if quality > 0 and dist > 0:
                    scan_buf.append((quality, angle, dist))
        finally:
            lidar.stop()
            lidar.disconnect()

    async def _update(self, points: list):
        async with self._state.lock:
            self._state.lidar_scan = points
