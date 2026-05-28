#!/bin/sh
# Create device nodes for any /dev/video* devices present on the host.
# The host's /dev is mounted read-only at /host-dev so we can inspect it
# without giving the container write access to the host's device tree.
# CAP_MKNOD (added in docker-compose.yml) lets us create the nodes here.
for i in 0 1 2 3; do
    HOST="/host-dev/video${i}"
    DEST="/dev/video${i}"
    if [ -c "$HOST" ] && [ ! -e "$DEST" ]; then
        MAJOR=$(printf '%d' "0x$(stat -c '%t' "$HOST" 2>/dev/null)" 2>/dev/null)
        MINOR=$(printf '%d' "0x$(stat -c '%T' "$HOST" 2>/dev/null)" 2>/dev/null)
        if [ "${MAJOR:-0}" -gt 0 ] 2>/dev/null; then
            mknod "$DEST" c "$MAJOR" "$MINOR" 2>/dev/null && chmod 660 "$DEST" 2>/dev/null || true
        fi
    fi
done

exec python -m daemon.main
