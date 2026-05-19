"""Camera capture loop and MJPEG frame management."""

import asyncio
import base64
import logging
import time

import cv2
import numpy as np

from .config import (
    CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, MJPEG_QUALITY
)
from .state import SharedState

log = logging.getLogger(__name__)

_JPEG_PARAMS = [cv2.IMWRITE_JPEG_QUALITY, MJPEG_QUALITY]


def _make_placeholder() -> bytes:
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
        # Seed with placeholder so get_current_jpeg() never returns empty bytes.
        self._state.camera_frame = _make_placeholder()

    async def run(self):
        """Run camera capture in a thread pool executor (OpenCV blocks)."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._capture_loop)

    def _capture_loop(self):
        interval = 1.0 / CAMERA_FPS

        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            log.warning(f"Camera {CAMERA_INDEX} not available — serving placeholder")
            # Keep the thread alive; placeholder was already set in __init__.
            while True:
                time.sleep(1.0)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS,          CAMERA_FPS)
        log.info(f"Camera {CAMERA_INDEX} opened at {CAMERA_WIDTH}×{CAMERA_HEIGHT} {CAMERA_FPS}fps")

        while True:
            t0 = time.monotonic()
            ok, frame = cap.read()
            if not ok:
                log.warning("Camera read failed")
                time.sleep(1.0)
                continue

            _, buf = cv2.imencode(".jpg", frame, _JPEG_PARAMS)
            jpeg_bytes = bytes(buf)

            # Direct assignment is safe: CPython's GIL makes a single pointer
            # swap atomic, which is sufficient for a video feed.
            self._state.camera_frame = jpeg_bytes
            self._state.camera_frame_b64 = base64.b64encode(jpeg_bytes).decode()

            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, interval - elapsed))

        cap.release()  # unreachable, but documents intent

    def get_current_jpeg(self) -> bytes:
        """Return the JPEG to serve to MJPEG clients right now."""
        if self._state.show_raw or self._state.camera_override is None:
            return self._state.camera_frame or b""
        return self._state.camera_override
