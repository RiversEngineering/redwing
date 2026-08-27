#!/bin/sh
# Create device nodes from the host's /dev (mounted read-only at /host-dev).
# CAP_MKNOD (in docker-compose.yml) allows mknod inside the container.
# A background watcher re-scans every 5 s so hot-plugged devices are picked up
# without restarting the container.

_mknod_if_present() {
    HOST="/host-dev/${1}"
    DEST="/dev/${1}"
    [ -c "$HOST" ] || return 0
    HOSTMM=$(stat -c '%t:%T' "$HOST" 2>/dev/null)
    MAJOR=$(printf '%d' "0x${HOSTMM%%:*}" 2>/dev/null)
    MINOR=$(printf '%d' "0x${HOSTMM##*:}" 2>/dev/null)
    [ "${MAJOR:-0}" -gt 0 ] 2>/dev/null || return 0
    if [ -e "$DEST" ]; then
        # Bus/device numbers (and, in principle, other dynamically-assigned
        # major:minor pairs) get reused as devices disconnect and reconnect —
        # confirmed on hardware: a Pico cycling through BOOTSEL<->app mode
        # repeatedly eventually left a stale node whose major:minor pointed
        # at a cdev the kernel had already destroyed, which open() reports as
        # ENODEV even though the file itself still exists. Refresh instead of
        # assuming "exists" means "still correct."
        DESTMM=$(stat -c '%t:%T' "$DEST" 2>/dev/null)
        DMAJOR=$(printf '%d' "0x${DESTMM%%:*}" 2>/dev/null)
        DMINOR=$(printf '%d' "0x${DESTMM##*:}" 2>/dev/null)
        if [ "$DMAJOR" = "$MAJOR" ] && [ "$DMINOR" = "$MINOR" ]; then
            return 0
        fi
        rm -f "$DEST" 2>/dev/null
    fi
    mkdir -p "$(dirname "$DEST")" 2>/dev/null
    mknod "$DEST" c "$MAJOR" "$MINOR" 2>/dev/null && chmod 660 "$DEST" 2>/dev/null || true
}

_refresh_devices() {
    # Camera (V4L2)
    for i in 0 1 2 3; do
        _mknod_if_present "video${i}"
    done

    # RP2040 (ttyACM — USB CDC serial)
    for i in 0 1 2 3; do
        _mknod_if_present "ttyACM${i}"
    done
    # Prefer the udev-managed /dev/rp2040 symlink from the host (requires the
    # 99-rp2040.rules udev rule to be installed).  Fall back to the first
    # available ttyACM if the udev rule hasn't run yet — this keeps the Pico
    # working even on a fresh Pi before the install script has been run.
    if [ -L "/host-dev/rp2040" ]; then
        TARGET=$(readlink "/host-dev/rp2040" 2>/dev/null)
        TARGET_NAME="${TARGET##*/}"
        if [ -e "/dev/$TARGET_NAME" ]; then
            ln -sf "/dev/$TARGET_NAME" /dev/rp2040 2>/dev/null || true
        fi
    elif [ ! -e "/dev/rp2040" ]; then
        for i in 0 1 2 3; do
            if [ -e "/dev/ttyACM${i}" ]; then
                ln -sf "/dev/ttyACM${i}" /dev/rp2040 2>/dev/null || true
                break
            fi
        done
    fi

    # LIDAR and other USB serial adapters (ttyUSB)
    for i in 0 1 2 3; do
        _mknod_if_present "ttyUSB${i}"
    done

    # I2C buses (battery monitor, HAT sensors)
    for i in 0 1 2 3 4 5; do
        _mknod_if_present "i2c-${i}"
    done
}

# Raw USB bus devices — picotool (via libusb) uses these to reset the RP2040
# into BOOTSEL mode over USB and to talk to its PICOBOOT interface once it
# re-enumerates there, so the dashboard can reflash it without a physical
# BOOTSEL button press. Bus/device numbers aren't stable names like
# ttyACM/video, so unlike the lookups above this mirrors every node currently
# on the host bus rather than one well-known path — this does widen the
# container's USB access beyond just the Pico. Kept as its own function (and
# polled separately below, briefly much faster during an active flash)
# because picotool's own "wait for the device to come back in BOOTSEL mode"
# patience window is well under a second — the general watcher's interval is
# too slow to win that race.
_refresh_usb_bus() {
    for busdir in /host-dev/bus/usb/*/; do
        [ -d "$busdir" ] || continue
        bus="$(basename "$busdir")"
        for dev in "${busdir}"*; do
            [ -e "$dev" ] || continue
            _mknod_if_present "bus/usb/${bus}/$(basename "$dev")"
        done
    done
}

# Initial scan at startup
_refresh_devices
_refresh_usb_bus

# Background watcher: re-scan every 5 s to pick up hot-plugged devices
# (camera, ttyACM/ttyUSB, I2C). Fine for these — nothing here needs to react
# faster than human hot-plug speed.
# After exec below, this process is reparented to PID 1 (the daemon) and runs
# until the container stops.
_device_watcher() {
    while true; do
        sleep 5
        _refresh_devices
    done
}
_device_watcher &

# Dedicated poller for the USB bus mirroring (see _refresh_usb_bus above).
# _mknod_if_present's stale-node check forks stat on every path it's given,
# every cycle, by design (that's the fix for the Pico-cycling-through-BOOTSEL
# bug) — so unlike the old create-if-missing version, this is never free, and
# polling the *entire* USB bus this way many times a second, for the whole
# life of the container, showed up on hardware as a large, continuous CPU/
# thermal cost (measured: ~470 forks/sec, ~35pp of container CPU) even though
# nothing was actually flashing. The sub-second reaction time only matters for
# picotool's own BOOTSEL-reenumeration window *during* an actual flash — the
# daemon touches FLASHING_FLAG_PATH (daemon/api.py, _do_flash_firmware) around
# the picotool calls, so fast polling only runs then; otherwise this idles at
# the same cadence as the general watcher above.
_usb_bus_watcher() {
    while true; do
        if [ -e /tmp/redwing_flashing ]; then
            sleep 0.1
        else
            sleep 5
        fi
        _refresh_usb_bus
    done
}
_usb_bus_watcher &

exec python -m daemon.main
