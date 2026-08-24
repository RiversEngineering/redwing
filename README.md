# redwing
Robotics Platform for Rivers Robotics

## Firmware

RP2040 firmware source lives in `firmware/`. Build it with the Pico SDK installed:

```
export PICO_SDK_PATH=/path/to/pico-sdk
firmware/build.sh
```

This produces `firmware/build/redwing.uf2`.

### Flashing from the dashboard

The dashboard's **Firmware** tab reflashes the RP2040 from that `.uf2` directly —
no need to unplug the Pico or hold BOOTSEL. It shells out to `picotool`, which
resets the Pico into its bootloader over USB, flashes it, and reboots it back
into the app.

Requirements:
- `firmware/build.sh` must have been run on the Pi at least once so
  `firmware/build/redwing.uf2` exists — the daemon container mounts that
  directory read-only (see `docker/docker-compose.yml`) and just flashes
  whatever's there. Rebuilding firmware and clicking **Flash** doesn't require
  restarting the container; the bind mount picks up the new file immediately.
- Flashing briefly disconnects the RP2040 (a few seconds); the daemon's
  existing serial reconnect logic reconnects automatically once it
  re-enumerates.

To flash manually instead: hold BOOTSEL while plugging in USB, then
drag-and-drop `firmware/build/redwing.uf2` onto the RPI-RP2 drive that appears.
