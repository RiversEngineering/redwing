"""Camera capture loop and MJPEG frame management."""

import asyncio
import base64
import logging

import cv2
import numpy as np

from .config import (
    CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, MJPEG_QUALITY
)
from .state import SharedState

log = logging.getLogger(__name__)

_JPEG_PARAMS = [cv2.IMWRITE_JPEG_QUALITY, MJPEG_QUALITY]
_NO_CAMERA_FRAME: bytes | None = None


def _make_no_camera_frame() -> bytes:
    img = np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), dtype=np.uint8)
    cv2.putText(
        img, "No Camera", (CAMERA_WIDTH // 2 - 90, CAMERA_HEIGHT // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (100, 100, 100), 2
    )
    _, buf = cv2.imencode(".jpg", img, _JPEG_PARAMS)
    return bytes(buf)


class CameraCapture:
    def __init__(self, state: SharedState):
        self._state = state

    async def run(self):
        """Run camera capture in a thread pool executor (OpenCV blocks)."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._capture_loop)

    def _capture_loop(self):
        global _NO_CAMERA_FRAME
        _NO_CAMERA_FRAME = _make_no_camera_frame()

        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            log.warning(f"Camera {CAMERA_INDEX} not available — dashboard will show placeholder")
            asyncio.get_event_loop().run_until_complete(self._set_frame(_NO_CAMERA_FRAME))
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS,          CAMERA_FPS)
        log.info(f"Camera {CAMERA_INDEX} opened at {CAMERA_WIDTH}×{CAMERA_HEIGHT} {CAMERA_FPS}fps")

        import time
        interval = 1.0 / CAMERA_FPS

        while True:
            t0 = time.monotonic()
            ok, frame = cap.read()
            if not ok:
                log.warning("Camera read failed")
                time.sleep(1.0)
                continue

            _, buf = cv2.imencode(".jpg", frame, _JPEG_PARAMS)
            jpeg_bytes = bytes(buf)

            # Also store a base64 version in state so library can read()
            b64 = base64.b64encode(jpeg_bytes).decode()

            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._store_raw(jpeg_bytes, b64))
            loop.close()

            elapsed = time.monotonic() - t0
            sleep_time = max(0.0, interval - elapsed)
            time.sleep(sleep_time)

        cap.release()

    async def _store_raw(self, jpeg_bytes: bytes, b64: str):
        async with self._state.lock:
            self._state.camera_frame = jpeg_bytes

    async def _set_frame(self, jpeg_bytes: bytes):
        async with self._state.lock:
            self._state.camera_frame = jpeg_bytes

    def get_current_jpeg(self) -> bytes:
        """Return the JPEG to serve to MJPEG clients right now."""
        # show_raw controls whether to serve raw camera or student-overridden frame
        if self._state.show_raw or self._state.camera_override is None:
            return self._state.camera_frame or (_NO_CAMERA_FRAME or b"")
        return self._state.camera_override
