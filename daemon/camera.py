"""Camera capture loop and MJPEG frame management."""

import asyncio
import base64
import logging
import time

import cv2
import numpy as np

from .config import (
    CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, MJPEG_QUALITY,
    OPENCV_THREADS,
)
from .state import SharedState

log = logging.getLogger(__name__)

# Cap OpenCV's thread pool for the feed. See OPENCV_THREADS in config.py —
# limiting it leaves cores free for other processes without slowing the feed.
cv2.setNumThreads(OPENCV_THREADS)

_JPEG_PARAMS = [cv2.IMWRITE_JPEG_QUALITY, MJPEG_QUALITY]

# If CAMERA_INDEX is -1, scan indices 0–3 and use the first one that opens.
_SCAN_INDICES = list(range(4))


def _make_placeholder(width: int, height: int) -> bytes:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(
        img, "No Camera", (width // 2 - 90, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (100, 100, 100), 2
    )
    _, buf = cv2.imencode(".jpg", img, _JPEG_PARAMS)
    return bytes(buf)


def _try_open(idx: int, fourcc: int, width: int, height: int, fps: int) -> cv2.VideoCapture | None:
    """Open one camera index and request a specific capture size/rate. Returns
    the opened capture (positioned after a successful warm-up read) or None."""
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    if not cap.isOpened():
        return None

    # Request MJPEG format before anything else.  Many USB cameras (e.g.
    # Arducam UC-844) default to YUYV, which hangs in select() at anything
    # above 640×480 because the USB bandwidth isn't enough. MJPEG delivers
    # compressed frames at any supported resolution.
    cap.set(cv2.CAP_PROP_FOURCC,       fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS,          fps)

    # Try up to 5 reads — camera may need a moment after format change.
    for _ in range(5):
        ok, _ = cap.read()
        if ok:
            return cap

    cap.release()
    return None


def _open_camera(width: int, height: int, fps: int) -> tuple[cv2.VideoCapture, int, int] | None:
    """Try to open a camera at the requested width/height/fps. Scans indices
    if CAMERA_INDEX == -1. Returns (cap, actual_width, actual_height) or None.

    Requests the target resolution directly first — decoding and re-encoding
    a full native-resolution MJPEG frame every cycle just to throw most of it
    away in a software resize is expensive (measured: ~80-90% of a Pi core,
    continuously). V4L2 never fabricates an arbitrary size; it always snaps
    to one of the camera's own discrete supported modes, so if the negotiated
    size comes back an exact match, that's proof the camera genuinely
    supports it (not a crop) and the resize in the capture loop below can be
    skipped entirely. If it doesn't match, fall back to the old behavior —
    request max resolution and resize in software — which is always correct
    for a camera whose modes we can't assume, just costlier.
    """
    candidates = [CAMERA_INDEX] if CAMERA_INDEX >= 0 else _SCAN_INDICES
    MJPEG = cv2.VideoWriter_fourcc(*'MJPG')

    for idx in candidates:
        cap = _try_open(idx, MJPEG, width, height, fps)
        if cap is not None:
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if actual_w == width and actual_h == height:
                log.info(f"Camera opened at index {idx} — native "
                         f"{width}×{height} mode @ {fps} fps, no software resize needed")
                return cap, actual_w, actual_h
            # Didn't get an exact match — this camera doesn't offer our
            # target size as a discrete mode (requesting it further down
            # could have cropped instead of scaled). Reopen fresh rather than
            # re-negotiate format on an already-streaming capture.
            cap.release()

        cap = _try_open(idx, MJPEG, 9999, 9999, fps)
        if cap is not None:
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            log.info(f"Camera opened at index {idx} — native {actual_w}×{actual_h}"
                     f", resized to {width}×{height} in software @ {fps} fps requested")
            return cap, actual_w, actual_h

    return None


class CameraCapture:
    def __init__(self, state: SharedState):
        self._state = state
        # Requested capture settings — mutable at runtime via request_config()
        # (dashboard System tab, for A/B testing resolution vs frame rate).
        # Not behind state.lock: the capture loop runs in a plain OS thread
        # (via run_in_executor below), and asyncio.Lock isn't meant to be
        # acquired off the event loop. Simple attribute reads/writes are
        # already atomic under the GIL — same reasoning as camera_frame
        # further down, which has done this safely all along.
        self._width  = CAMERA_WIDTH
        self._height = CAMERA_HEIGHT
        self._fps    = CAMERA_FPS
        self._generation = 0   # bumped by request_config to force a reopen

        # Seed with placeholder so get_current_jpeg() never returns empty bytes.
        self._state.camera_frame = _make_placeholder(self._width, self._height)
        self._state.camera_config = {
            "width": self._width, "height": self._height, "fps": self._fps,
            "actual_width": None, "actual_height": None,
        }
        self._state.camera_actual_fps = None

    def request_config(self, width: int, height: int, fps: int):
        """Change the requested capture resolution/frame rate. Takes effect
        on the capture loop's next iteration (it reopens the camera fresh —
        resolution and fps are negotiated together at open time, same as the
        initial connect). Not persisted — resets to config.py defaults on
        daemon restart, since this is meant for live A/B testing rather than
        a permanent per-robot setting.
        """
        self._width  = width
        self._height = height
        self._fps    = fps
        self._generation += 1
        self._state.camera_frame = _make_placeholder(width, height)
        self._state.camera_config = {
            "width": width, "height": height, "fps": fps,
            "actual_width": None, "actual_height": None,
        }
        self._state.camera_actual_fps = None

    async def run(self):
        """Run camera capture in a thread pool executor (OpenCV blocks)."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._capture_loop)

    def _capture_loop(self):
        cap = None
        cap_generation = None
        interval = 1.0 / self._fps
        target_w = target_h = None
        last_frame_time = None
        fps_ema = None   # exponential moving average of measured capture fps

        while True:
            # ── Connect (or reconnect, or apply a new requested config) ──────
            if cap is None or cap_generation != self._generation:
                if cap is not None:
                    cap.release()
                cap_generation = self._generation
                target_w, target_h, target_fps = self._width, self._height, self._fps
                interval = 1.0 / target_fps
                last_frame_time = None
                fps_ema = None

                result = _open_camera(target_w, target_h, target_fps)
                if result is None:
                    cap = None
                    log.warning("No camera found — will retry in 5 s")
                    time.sleep(5.0)
                    continue
                cap, actual_w, actual_h = result
                self._state.camera_config = {
                    "width": target_w, "height": target_h, "fps": target_fps,
                    "actual_width": actual_w, "actual_height": actual_h,
                }

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
            if w != target_w or h != target_h:
                src_ar = w / h
                dst_ar = target_w / target_h
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
                frame = cv2.resize(frame, (target_w, target_h),
                                   interpolation=cv2.INTER_AREA)

            _, buf = cv2.imencode(".jpg", frame, _JPEG_PARAMS)
            jpeg_bytes = bytes(buf)

            # Direct assignment is safe: CPython's GIL makes a single pointer
            # swap atomic, which is sufficient for a video feed.
            self._state.camera_frame = jpeg_bytes
            self._state.camera_frame_b64 = base64.b64encode(jpeg_bytes).decode()

            # Measured capture rate — lets the dashboard show what's actually
            # being achieved, not just what was requested (camera/CPU limits
            # may not deliver it), for A/B testing resolution vs frame rate.
            now = time.monotonic()
            if last_frame_time is not None:
                dt = now - last_frame_time
                if dt > 0:
                    inst_fps = 1.0 / dt
                    fps_ema = inst_fps if fps_ema is None else (fps_ema * 0.9 + inst_fps * 0.1)
                    self._state.camera_actual_fps = round(fps_ema, 1)
            last_frame_time = now

            elapsed = now - t0
            time.sleep(max(0.0, interval - elapsed))

    def get_current_jpeg(self) -> bytes:
        """Return the JPEG to serve to MJPEG clients right now."""
        if self._state.show_raw or self._state.camera_override is None:
            return self._state.camera_frame or b""
        return self._state.camera_override
