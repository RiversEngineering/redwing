"""Physical gamepad reader using evdev (Linux input subsystem).

Runs as a long-lived asyncio task. Continuously scans for a connected
gamepad (USB dongle or Bluetooth), reads its events, and updates
SharedState.gamepad. When the controller disconnects the state is reset
to all-zero and scanning resumes.

Tested with the GameSir Nova Lite (2.4 GHz USB dongle, Xbox-compatible
HID layout). Should work with any Xbox-compatible gamepad on Linux.
"""

import asyncio
import logging

log = logging.getLogger(__name__)

# Deadzone applied after hardware flat region
_DEADZONE = 0.08

# Standard Xbox / HID gamepad button codes (evdev BTN_*)
_BTN_A  = 304   # BTN_SOUTH
_BTN_B  = 305   # BTN_EAST
_BTN_X  = 307   # BTN_WEST
_BTN_Y  = 308   # BTN_NORTH
_BTN_LB = 310   # BTN_TL  (left bumper)
_BTN_RB = 311   # BTN_TR  (right bumper)
_BTN_LT = 312   # BTN_TL2 (left trigger, digital — Switch mode and some HID controllers)
_BTN_RT = 313   # BTN_TR2 (right trigger, digital — Switch mode and some HID controllers)

# Nintendo Switch Pro Controller D-pad (hid-nintendo driver maps these as
# individual buttons rather than ABS_HAT0X/Y on some kernel versions)
_BTN_DPAD_UP    = 544   # BTN_DPAD_UP
_BTN_DPAD_DOWN  = 545   # BTN_DPAD_DOWN
_BTN_DPAD_LEFT  = 546   # BTN_DPAD_LEFT
_BTN_DPAD_RIGHT = 547   # BTN_DPAD_RIGHT


def _normalize(value: int, info) -> float:
    """Map a raw axis value to -1.0 .. +1.0 with deadzone."""
    mid  = (info.min + info.max) / 2.0
    half = (info.max - info.min) / 2.0
    if half == 0:
        return 0.0
    n = (value - mid) / half
    # Combine hardware flat region with our software deadzone
    deadzone = max(_DEADZONE, info.flat / half)
    if abs(n) < deadzone:
        return 0.0
    sign = 1.0 if n > 0 else -1.0
    return round(sign * (abs(n) - deadzone) / (1.0 - deadzone), 3)


def _find_gamepad(evdev):
    """Return the first InputDevice that looks like a gamepad, or None."""
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            caps = dev.capabilities()
            ev_abs = evdev.ecodes.EV_ABS
            ev_key = evdev.ecodes.EV_KEY
            if ev_abs in caps and ev_key in caps:
                keys = caps.get(ev_key, [])
                # Flatten (code, [aliases]) tuples that evdev sometimes returns
                flat_keys = []
                for k in keys:
                    if isinstance(k, int):
                        flat_keys.append(k)
                    else:
                        flat_keys.extend(k) if hasattr(k, '__iter__') else flat_keys.append(k)
                if evdev.ecodes.BTN_SOUTH in flat_keys:
                    return dev
            dev.close()
        except Exception:
            pass
    return None


async def gamepad_reader_task(state) -> None:
    """Top-level task — never raises, keeps retrying after disconnects."""
    try:
        import evdev
        from evdev import ecodes
    except ImportError:
        log.warning("evdev not installed — physical gamepad support disabled")
        return

    loop = asyncio.get_event_loop()

    while True:
        device = await loop.run_in_executor(None, _find_gamepad, evdev)
        if device is None:
            await asyncio.sleep(2.0)
            continue

        log.info(f"Gamepad connected: {device.name}")

        # Build abs_info dict: {axis_code: AbsInfo}
        caps = device.capabilities(absinfo=True)
        abs_info = {}
        for code, info in caps.get(ecodes.EV_ABS, []):
            abs_info[code] = info

        async with state.lock:
            state.gamepad.connected = True
            state.gamepad.source = "physical"

        try:
            async for event in device.async_read_loop():
                if event.type == ecodes.EV_ABS:
                    info = abs_info.get(event.code)
                    if info is None:
                        continue
                    async with state.lock:
                        gp = state.gamepad
                        if event.code == ecodes.ABS_X:
                            gp.lx = _normalize(event.value, info)
                        elif event.code == ecodes.ABS_Y:
                            gp.ly = -_normalize(event.value, info)
                        elif event.code == ecodes.ABS_RX:
                            gp.rx = _normalize(event.value, info)
                        elif event.code == ecodes.ABS_RY:
                            gp.ry = -_normalize(event.value, info)
                        elif event.code == ecodes.ABS_HAT0X:
                            gp.left  = (event.value == -1)
                            gp.right = (event.value ==  1)
                        elif event.code == ecodes.ABS_HAT0Y:
                            gp.up   = (event.value == -1)
                            gp.down = (event.value ==  1)
                        elif event.code == ecodes.ABS_Z:
                            # Left trigger analog (0..max → 0.0..1.0)
                            gp.lt = round(event.value / max(info.max, 1), 3)
                        elif event.code == ecodes.ABS_RZ:
                            # Right trigger analog
                            gp.rt = round(event.value / max(info.max, 1), 3)

                elif event.type == ecodes.EV_KEY:
                    async with state.lock:
                        gp = state.gamepad
                        pressed = bool(event.value)
                        if event.code == _BTN_A:
                            gp.a = pressed
                        elif event.code == _BTN_B:
                            gp.b = pressed
                        elif event.code == _BTN_X:
                            gp.x = pressed
                        elif event.code == _BTN_Y:
                            gp.y = pressed
                        elif event.code == _BTN_LB:
                            gp.lb = pressed
                        elif event.code == _BTN_RB:
                            gp.rb = pressed
                        elif event.code == _BTN_LT:
                            gp.lt = 1.0 if pressed else 0.0
                        elif event.code == _BTN_RT:
                            gp.rt = 1.0 if pressed else 0.0
                        elif event.code == _BTN_DPAD_UP:
                            gp.up = pressed
                        elif event.code == _BTN_DPAD_DOWN:
                            gp.down = pressed
                        elif event.code == _BTN_DPAD_LEFT:
                            gp.left = pressed
                        elif event.code == _BTN_DPAD_RIGHT:
                            gp.right = pressed

        except OSError:
            log.info(f"Gamepad disconnected: {device.name}")
        except Exception as exc:
            log.warning(f"Gamepad read error: {exc}")
        finally:
            try:
                device.close()
            except Exception:
                pass

        async with state.lock:
            state.gamepad.reset()

        await asyncio.sleep(1.0)
