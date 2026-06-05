#!/bin/sh
# Create device nodes from the host's /dev (mounted read-only at /host-dev).
# CAP_MKNOD (in docker-compose.yml) allows mknod inside the container.
# Missing devices are silently skipped so the container always starts.

_mknod_if_present() {
    HOST="/host-dev/${1}"
    DEST="/dev/${1}"
    if [ -c "$HOST" ] && [ ! -e "$DEST" ]; then
        MAJOR=$(printf '%d' "0x$(stat -c '%t' "$HOST" 2>/dev/null)" 2>/dev/null)
        MINOR=$(printf '%d' "0x$(stat -c '%T' "$HOST" 2>/dev/null)" 2>/dev/null)
        if [ "${MAJOR:-0}" -gt 0 ] 2>/dev/null; then
            mknod "$DEST" c "$MAJOR" "$MINOR" 2>/dev/null && chmod 660 "$DEST" 2>/dev/null || true
        fi
    fi
}

# Camera (V4L2 video devices)
for i in 0 1 2 3; do
    _mknod_if_present "video${i}"
done

# RP2040 (ttyACM — USB CDC serial)
for i in 0 1 2 3; do
    _mknod_if_present "ttyACM${i}"
done
# /dev/rp2040 is a udev symlink on the host; recreate it inside the container.
if [ -L "/host-dev/rp2040" ]; then
    TARGET=$(readlink "/host-dev/rp2040" 2>/dev/null)
    TARGET_NAME="${TARGET##*/}"   # strip /dev/ prefix
    if [ -e "/dev/$TARGET_NAME" ]; then
        ln -sf "/dev/$TARGET_NAME" /dev/rp2040 2>/dev/null || true
    fi
fi

# LIDAR and other USB serial adapters (ttyUSB)
for i in 0 1 2 3; do
    _mknod_if_present "ttyUSB${i}"
done

# I2C buses (battery monitor, HAT sensors)
for i in 0 1 2 3 4 5; do
    _mknod_if_present "i2c-${i}"
done

exec python -m daemon.main
