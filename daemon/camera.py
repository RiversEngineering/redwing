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

# If CAMERA_INDEX is -1, scan indices 0–3 and use the first one that opens.
_SCAN_INDICES = list(range(4))


def _make_placeholder() -> bytes:
    img = np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), dtype=np.uint8)
    cv2.putText(
        img, "No Camera", (CAMERA_WIDTH // 2 - 90, CAMERA_HEIGHT // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (100, 100, 100), 2
    )
    _, buf = cv2.imencode(".jpg", img, _JPEG_PARAMS)
    return bytes(buf)


def _open_camera() -> cv2.VideoCapture | None:
    """Try to open a camera. Scans indices if CAMERA_INDEX == -1."""
    candidates = [CAMERA_INDEX] if CAMERA_INDEX >= 0 else _SCAN_INDICES
    MJPEG = cv2.VideoWriter_fourcc(*'MJPG')

    for idx in candidates:
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if not cap.isOpened():
            continue

        # Request MJPEG format before anything else.  Many USB cameras
        # (e.g. Arducam UC-844) default to YUYV, which hangs in select()
        # at anything above 640×480 because the USB bandwidth isn't enough.
        # MJPEG delivers compressed frames at any supported resolution.
        cap.set(cv2.CAP_PROP_FOURCC,       MJPEG)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  9999)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 9999)
        cap.set(cv2.CAP_PROP_FPS,          CAMERA_FPS)

        # Try up to 5 reads — camera may need a moment after format change.
        ok = False
        for _ in range(5):
            ok, _ = cap.read()
            if ok:
                break

        if ok:
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            log.info(f"Camera opened at index {idx} — native {actual_w}×{actual_h}"
                     f", resized to {CAMERA_WIDTH}×{CAMERA_HEIGHT} in software")
            return cap

        cap.release()
    return None


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
        cap = None

        while True:
            # ── Connect (or reconnect) ────────────────────────────────────────
            if cap is None:
                cap = _open_camera()
                if cap is None:
                    log.warning("No camera found — will retry in 5 s")
                    time.sleep(5.0)
                    continue

            # ── Capture frame ─────────────────────────────────────────────────
            t0 = time.monotonic()
            ok, frame = cap.read()
            if not ok:
                log.warning("Camera read failed — reopening in 2 s")
                cap.release()
                cap = None
                time.sleep(2.0)
                continue

            # Resize to target resolution in software.  Do NOT rely on
            # cap.set(CAP_PROP_FRAME_WIDTH/HEIGHT) to scale — many cameras
            # satisfy the request by cropping from the top-left corner of
            # the sensor instead, showing only a portion of the image.
            # Crop to the target aspect ratio first so a wide-sensor camera
            # (e.g. 1920×1200 = 16:10) doesn't squish into a 4:3 output.
            h, w = frame.shape[:2]
            if w != CAMERA_WIDTH or h != CAMERA_HEIGHT:
                src_ar = w / h
                dst_ar = CAMERA_WIDTH / CAMERA_HEIGHT
                if src_ar > dst_ar:
                    # Source is wider — trim left and right equally
                    new_w = int(h * dst_ar)
                    x0 = (w - new_w) // 2
                    frame = frame[:, x0:x0 + new_w]
                elif src_ar < dst_ar:
                    # Source is taller — trim top and bottom equally
                    new_h = int(w / dst_ar)
                    y0 = (h - new_h) // 2
                    frame = frame[y0:y0 + new_h, :]
                frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT),
                                   interpolation=cv2.INTER_AREA)

            _, buf = cv2.imencode(".jpg", frame, _JPEG_PARAMS)
            jpeg_bytes = bytes(buf)

            # Direct assignment is safe: CPython's GIL makes a single pointer
            # swap atomic, which is sufficient for a video feed.
            self._state.camera_frame = jpeg_bytes
            self._state.camera_frame_b64 = base64.b64encode(jpeg_bytes).decode()

            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, interval - elapsed))

    def get_current_jpeg(self) -> bytes:
        """Return the JPEG to serve to MJPEG clients right now."""
        if self._state.show_raw or self._state.camera_override is None:
            return self._state.camera_frame or b""
        return self._state.camera_override
