"""FastAPI web application — dashboard WebSocket, MJPEG stream, REST."""

import asyncio
import base64
import logging
import os
from typing import AsyncIterator, TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
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

# Sentinel file entrypoint-daemon.sh watches to know when to switch its USB-bus
# device-node mirror into fast (100ms) polling — see _do_flash_firmware below.
FLASHING_FLAG_PATH = "/tmp/redwing_flashing"


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
                # CMD_STOP_ALL only cuts motor-type ports — firmware leaves servos
                # at their last commanded pulse. A servo in goBILDA continuous
                # mode is really acting as a motor though, so give it an explicit
                # neutral (stop) pulse here, on both physical ports and PCA9685
                # channels (which CMD_STOP_ALL never reaches at all).
                async with state.lock:
                    continuous_ports = [
                        int(pid) for pid, pd in state.ports.items()
                        if pd.get("type") == "servo" and pd.get("gobilda_mode") == "continuous"
                    ]
                for port in continuous_ports:
                    rp.enqueue(proto.cmd_set_servo(port, 1500))
                if pca and pca.present:
                    async with state.lock:
                        continuous_channels = [
                            ch for ch, cd in state.pca9685_channels.items()
                            if cd.get("type") == "servo" and cd.get("gobilda_mode") == "continuous"
                        ]
                        paired_magnitude_channels = [
                            ch for ch, cd in state.pca9685_channels.items()
                            if cd.get("type") == "motor_sm_pair" and cd.get("role") == "magnitude"
                        ]
                    for ch in continuous_channels:
                        pca.set_channel_pulse_us(ch, 1500)
                        async with state.lock:
                            state.pca9685_channels.setdefault(ch, {})["pulse_us"] = 1500
                    for ch in paired_magnitude_channels:
                        # Zero the magnitude (PWM) channel only — direction is
                        # a static level and stopping doesn't imply a
                        # direction change.
                        pca.set_channel_duty(ch, 0)
                        async with state.lock:
                            cd = state.pca9685_channels.setdefault(ch, {})
                            cd["duty_pct"] = 0
                            cd["value"] = 0

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

            elif cmd == "set_camera_config":
                # Runtime-only (not persisted) — lets the dashboard's System
                # tab A/B test resolution vs. frame rate; resets to config.py
                # defaults on daemon restart. See CameraCapture.request_config.
                width  = int(msg.get("width", 640))
                height = int(msg.get("height", 480))
                fps    = int(msg.get("fps", 30))
                if not (160 <= width <= 1920 and 120 <= height <= 1200 and 1 <= fps <= 120):
                    async with state.lock:
                        state.add_log("error", "[Dashboard] Invalid camera config")
                    return
                camera.request_config(width, height, fps)
                async with state.lock:
                    state.add_log("info", f"[Dashboard] Camera reconfiguring to {width}×{height} @ {fps} fps")

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
                if pca and pca.mode == "motor":
                    # Both types are RC servo/ESC signals (500-2500 us pulses)
                    # and need a 50 Hz frame to fit in — motor mode runs the
                    # whole chip at ~1 kHz (a 1000 us period), which can't
                    # represent them at all.
                    async with state.lock:
                        state.add_log("error", f"[Dashboard] PCA9685 is in motor mode (~1 kHz) — RC servo/ESC signals need Servo mode")
                    return
                async with state.lock:
                    if state.pca9685_channels.get(channel, {}).get("type") == "motor_sm_pair":
                        state.add_log("error", f"[Dashboard] PCA P{channel} is part of a paired motor — Reset it first")
                        return
                if not pca or not pca.present:
                    async with state.lock:
                        state.add_log("warning", "[Dashboard] PCA9685 not detected")
                    return
                pca.configure_channel(channel, port_type)
                async with state.lock:
                    state.pca9685_channels[channel] = {"type": port_type, "pulse_us": 1500}
                    state.add_log("info", f"[Dashboard] PCA P{channel} configured as {port_type}")

            elif cmd == "pca_reset_channel":
                # Unlike RP2040 ports, a PCA9685 channel is pure daemon-side
                # bookkeeping — no firmware "no per-port reset" limitation
                # applies, so this can just clear the one channel directly.
                # A paired channel (see pca_pair_channels) is meaningless on
                # its own, so resetting either half releases both.
                channel = int(msg["channel"])
                async with state.lock:
                    cd = state.pca9685_channels.get(channel, {})
                    partner = cd.get("partner") if cd.get("type") == "motor_sm_pair" else None
                channels = [channel] + ([partner] if partner is not None else [])
                if pca and pca.present:
                    for ch in channels:
                        pca.set_channel_off(ch)
                async with state.lock:
                    for ch in channels:
                        state.pca9685_channels.pop(ch, None)
                    state.add_log("info", f"[Dashboard] PCA {'+'.join(f'P{ch}' for ch in channels)} reset")

            elif cmd == "pca_set_motor":
                channel  = int(msg["channel"])
                val_x100 = int(max(-10000, min(10000, float(msg.get("value_pct", 0)) * 100)))
                if pca and pca.present:
                    pulse_us = 1500 + (val_x100 * 400) // 10000
                    pca.set_channel_pulse_us(channel, pulse_us)
                    async with state.lock:
                        state.pca9685_channels.setdefault(channel, {})["pulse_us"] = pulse_us

            elif cmd == "pca_pair_channels":
                # Bind two PCA9685 channels together as one sign-magnitude
                # motor, mirroring the D-port motor_sm scheme in software:
                # channel_a carries a duty cycle proportional to |speed| (a
                # plain PWM+DIR driver's PWM input, e.g. Cytron MDD10A
                # Sign-Magnitude mode — 0% duty -> stopped; see
                # pca.set_channel_duty for why this is NOT the RC-style pulse
                # used for servos/ESCs), channel_b is held at a fixed 0% or
                # 100% duty level via the PCA9685's full-on/full-off register
                # bits (pca.set_channel_level) — a true static high/low
                # level — for the driver's DIR input.
                channel_a = int(msg["channel_a"])  # magnitude / PWM
                channel_b = int(msg["channel_b"])  # direction / DIR
                if channel_a == channel_b or not (0 <= channel_a < 16 and 0 <= channel_b < 16):
                    async with state.lock:
                        state.add_log("error", "[Dashboard] Invalid PCA channel pair")
                    return
                async with state.lock:
                    if state.pca9685_channels.get(channel_a) or state.pca9685_channels.get(channel_b):
                        state.add_log("error", f"[Dashboard] PCA P{channel_a}/P{channel_b} must both be unconfigured before pairing")
                        return
                if not pca or not pca.present:
                    async with state.lock:
                        state.add_log("warning", "[Dashboard] PCA9685 not detected")
                    return
                pca.set_channel_duty(channel_a, 0)       # 0% magnitude — stopped
                pca.set_channel_level(channel_b, True)   # arbitrary default direction
                async with state.lock:
                    state.pca9685_channels[channel_a] = {
                        "type": "motor_sm_pair", "role": "magnitude", "partner": channel_b,
                        "duty_pct": 0, "value": 0,
                    }
                    state.pca9685_channels[channel_b] = {
                        "type": "motor_sm_pair", "role": "direction", "partner": channel_a,
                        "level": True,
                    }
                    state.add_log("info", f"[Dashboard] PCA P{channel_a}+P{channel_b} paired as sign-magnitude motor")

            elif cmd == "pca_set_pair_motor":
                # channel = the magnitude-role channel (the pair's "handle").
                # The direction-role partner is looked up rather than
                # requiring the dashboard to track both channel numbers.
                channel  = int(msg["channel"])
                val_x100 = int(max(-10000, min(10000, float(msg.get("value_pct", 0)) * 100)))
                async with state.lock:
                    cd = state.pca9685_channels.get(channel)
                    if not cd or cd.get("type") != "motor_sm_pair" or cd.get("role") != "magnitude":
                        state.add_log("error", f"[Dashboard] PCA P{channel} is not a paired motor's magnitude channel")
                        return
                    partner = cd["partner"]
                if pca and pca.present:
                    mag_duty  = abs(val_x100) / 100.0   # 0-100%
                    dir_level = val_x100 >= 0
                    pca.set_channel_duty(channel, mag_duty)
                    pca.set_channel_level(partner, dir_level)
                    async with state.lock:
                        cd = state.pca9685_channels.setdefault(channel, {})
                        cd["duty_pct"] = mag_duty
                        cd["value"] = val_x100
                        pd = state.pca9685_channels.setdefault(partner, {})
                        pd["level"] = dir_level

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

            elif cmd == "set_servo_gobilda_interface":
                # Switches how the dashboard (and subsequent set_servo commands)
                # interpret this port — units, slider range, and pulse mapping —
                # independent of whether the physical servo has actually been
                # reprogrammed. Positional/Continuous call this immediately;
                # only Program (gobilda_set_mode, below) touches real hardware.
                port = int(msg["port"])
                mode = str(msg.get("mode", "positional"))
                async with state.lock:
                    pd = state.ports.setdefault(str(port), {})
                    pd["gobilda_mode"] = "continuous" if mode == "continuous" else "positional"
                    if mode == "continuous":
                        pd["min_angle"] = -100.0; pd["max_angle"] = 100.0
                        pd["min_pulse_us"] = 900; pd["max_pulse_us"] = 2100
                    else:
                        pd["min_angle"] = 0.0; pd["max_angle"] = 300.0
                        pd["min_pulse_us"] = 500; pd["max_pulse_us"] = 2500

            elif cmd == "gobilda_set_mode":
                # Program: the ONLY thing this does is reprogram the servo's
                # internal mode over its serial line. The interface (units,
                # range) already switched separately via
                # set_servo_gobilda_interface — this just records what mode
                # was actually sent to hardware, for the Program button's own
                # enabled/disabled state.
                port = int(msg["port"])
                mode = str(msg.get("mode", "positional"))
                rp.enqueue(proto.cmd_gobilda_mode(port, 1 if mode == "continuous" else 0))
                async with state.lock:
                    pd = state.ports.setdefault(str(port), {})
                    pd["gobilda_programmed_mode"] = mode

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

            elif cmd == "pca_set_gobilda_mode":
                # Software-only equivalent of gobilda_set_mode: PCA9685 channels
                # are plain PWM outputs with no serial line back to the servo,
                # so there's no physical mode reprogram to send — this just
                # tells the daemon (and Stop All) how to interpret this
                # channel's pulses, matching the S-port continuous convention.
                ch   = int(msg["channel"])
                mode = str(msg.get("mode", "positional"))
                async with state.lock:
                    cd = state.pca9685_channels.get(ch)
                    if not cd or cd.get("type") != "servo":
                        state.add_log("error", f"[Dashboard] PCA P{ch} must be configured as Servo before setting continuous mode")
                        return
                    cd["gobilda_mode"] = "continuous" if mode == "continuous" else "positional"
                    if mode == "continuous":
                        cd["min_angle"] = -100.0; cd["max_angle"] = 100.0
                        cd["min_pulse_us"] = 900; cd["max_pulse_us"] = 2100
                    else:
                        cd["min_angle"] = 0.0; cd["max_angle"] = 300.0
                        cd["min_pulse_us"] = 500; cd["max_pulse_us"] = 2500

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

            elif cmd == "pca_set_mode":
                # PWM frequency is chip-wide on the PCA9685 (no per-channel
                # rate), so switching modes always resets every channel —
                # each one's existing pulse/duty/level programming stops
                # meaning what it used to the moment the frequency changes.
                # The dashboard is expected to confirm this with the user
                # first when channels are already configured.
                mode = str(msg.get("mode", "servo"))
                if mode not in ("servo", "motor"):
                    async with state.lock:
                        state.add_log("error", "[Dashboard] PCA mode must be servo or motor")
                    return
                if not pca or not pca.present:
                    async with state.lock:
                        state.add_log("warning", "[Dashboard] PCA9685 not detected")
                    return
                ok = await pca.set_mode(mode)
                async with state.lock:
                    if ok:
                        state.pca9685_channels.clear()
                        state.add_log("info", f"[Dashboard] PCA9685 switched to {mode} mode ({pca.target_hz:.0f} Hz) — all channels reset")
                    else:
                        state.add_log("error", "[Dashboard] PCA9685 mode switch failed (not responding)")

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

    async def _run_picotool(*args: str) -> int:
        """Run picotool with the given args, streaming its output via _flash_log.

        Returns the exit code. Raises FileNotFoundError if picotool itself
        isn't installed (a distinct condition from picotool running and
        failing, which just yields a non-zero return code).
        """
        proc = await asyncio.create_subprocess_exec(
            "picotool", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode(errors="replace").rstrip()
            if text:
                await _flash_log("info", f"[picotool] {text}")
        return await proc.wait()

    async def _do_flash_firmware(clients: set) -> tuple[bool, str]:
        """Reflash the RP2040 from the on-disk .uf2 via picotool.

        This runs picotool TWICE, deliberately, as two separate OS processes:

        1. `load -f -x` on the currently-running app — its -f flag resets the
           Pico into BOOTSEL over USB (Pico SDK's reset-via-vendor-interface,
           no physical button needed). This first run is expected to report
           "no accessible devices found" and a non-zero exit — confirmed on
           hardware that a single picotool process's device list goes stale
           after its first scan and never notices the Pico reappear under a
           new USB address mid-run, no matter what container capabilities are
           granted. Its exit code is intentionally ignored; only the reboot
           side-effect (already reliably confirmed via host-side USB traces)
           matters here.
        2. A brand-new `load -x` process, run fresh once step 1 has finished
           (which, thanks to step 1's own ~6s of futile retrying, is already
           well after the Pico has settled into BOOTSEL). A fresh process's
           first device scan is a real, correct USB topology walk — this is
           the run that actually writes the firmware and whose result is what
           gets reported to the dashboard.

        The daemon's existing serial reconnect loop (rp2040.py) picks the Pico
        back up automatically once it re-enumerates as a CDC device again
        after step 2 reboots it back into the app.

        Returns (success, message) — used by the HTTP endpoint below to give
        Ansible a real pass/fail result instead of a fire-and-forget request.
        """
        flash_state["running"] = True
        # Signal entrypoint-daemon.sh's USB-bus watcher to switch into its fast
        # (100ms) polling mode — it only needs to win picotool's sub-second
        # BOOTSEL-reenumeration race during an actual flash, not for the
        # entire life of the container. See entrypoint-daemon.sh.
        open(FLASHING_FLAG_PATH, "w").close()
        try:
            await _broadcast_flash_status(clients, "running", "Flashing firmware...")
            await _flash_log("info", "[Dashboard] Flashing firmware...")

            if not os.path.isfile(FIRMWARE_UF2_PATH):
                msg = f"Firmware file not found: {FIRMWARE_UF2_PATH}"
                await _flash_log("error", f"[Dashboard] {msg}")
                await _broadcast_flash_status(clients, "error", msg)
                return False, msg

            try:
                await _flash_log("info", "[Dashboard] Requesting reboot into BOOTSEL mode...")
                await _run_picotool("load", "-f", "-x", FIRMWARE_UF2_PATH)

                await _flash_log("info", "[Dashboard] Flashing from a fresh picotool run...")
                rc = await _run_picotool("load", "-x", FIRMWARE_UF2_PATH)
            except FileNotFoundError:
                msg = "picotool not found — is it installed in the daemon image?"
                await _flash_log("error", f"[Dashboard] {msg}")
                await _broadcast_flash_status(clients, "error", msg)
                return False, msg

            if rc == 0:
                msg = "Firmware flashed successfully"
                await _flash_log("info", f"[Dashboard] {msg}")
                await _broadcast_flash_status(clients, "success", "Firmware flashed successfully.")
                return True, msg
            else:
                msg = f"picotool exited with code {rc}"
                await _flash_log("error", f"[Dashboard] {msg}")
                await _broadcast_flash_status(clients, "error", msg)
                return False, msg
        except Exception as exc:
            log.exception("Firmware flash failed")
            await _flash_log("error", f"[Dashboard] Flash failed: {exc}")
            await _broadcast_flash_status(clients, "error", str(exc))
            return False, str(exc)
        finally:
            flash_state["running"] = False
            try:
                os.remove(FLASHING_FLAG_PATH)
            except FileNotFoundError:
                pass

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

    @app.post("/flash_firmware")
    async def flash_firmware():
        """Reflash the RP2040 from the on-disk .uf2, blocking until done.

        For Ansible (see ansible/playbooks/flash_firmware.yml) — unlike the
        dashboard's WebSocket "flash_firmware" command, which fires the flash
        in the background and streams progress back over the socket, this
        waits for the real result so a caller with no open WebSocket (like an
        ansible.builtin.uri task) gets an honest pass/fail.
        """
        if flash_state["running"]:
            return JSONResponse(
                {"ok": False, "message": "Firmware flash already in progress"},
                status_code=409,
            )
        ok, message = await _do_flash_firmware(ws_clients)
        return JSONResponse({"ok": ok, "message": message}, status_code=200 if ok else 500)

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
