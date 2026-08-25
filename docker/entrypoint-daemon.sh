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

    _refresh_usb_bus
}

# Raw USB bus devices — picotool (via libusb) uses these to reset the RP2040
# into BOOTSEL mode over USB and to talk to its PICOBOOT interface once it
# re-enumerates there, so the dashboard can reflash it without a physical
# BOOTSEL button press. Bus/device numbers aren't stable names like
# ttyACM/video, so unlike the lookups above this mirrors every node currently
# on the host bus rather than one well-known path — this does widen the
# container's USB access beyond just the Pico. Kept as its own function (and
# polled separately, much faster, below) because picotool's own "wait for the
# device to come back in BOOTSEL mode" patience window is well under a
# second — the general 1 s device watcher was too slow to win that race.
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

# Background watcher: re-scan every 1 s to pick up hot-plugged devices
# (camera, ttyACM/ttyUSB, I2C). Fine for these — nothing here needs to react
# faster than human hot-plug speed.
# After exec below, this process is reparented to PID 1 (the daemon) and runs
# until the container stops.
_device_watcher() {
    while true; do
        sleep 1
        _refresh_devices
    done
}
_device_watcher &

# Dedicated fast poller just for the USB bus mirroring — see comment on
# _refresh_usb_bus above for why this needs a much tighter interval than the
# general watcher. The fast path (device already mirrored) is a cheap `[ -e ]`
# test with no forked processes, so polling this often costs very little.
_usb_bus_watcher() {
    while true; do
        sleep 0.1
        _refresh_usb_bus
    done
}
_usb_bus_watcher &

exec python -m daemon.main
