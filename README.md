# redwing
Robotics Platform for Rivers Robotics

## Firmware

RP2040 firmware source lives in `firmware/`. Build it with the Pico SDK installed:

```
export PICO_SDK_PATH=/path/to/pico-sdk
firmware/build.sh
```

This produces `firmware/build/redwing.uf2` (a full CMake work directory —
gitignored) and copies the result to **`firmware/redwing.uf2`**, a stable,
git-tracked path.

**Whenever you build new firmware you intend to ship, commit and push
`firmware/redwing.uf2`.** Every Pi already pulls this repo via git/`install.sh`,
so a plain `git pull` (or the dashboard's Update flow, if you have one) is
enough to get the new build onto a robot — no Pico SDK or ARM toolchain needs
to be installed on the Pi itself.

### Flashing from the dashboard

The dashboard's **Firmware** tab reflashes the RP2040 from `firmware/redwing.uf2`
directly — no need to unplug the Pico or hold BOOTSEL. It shells out to
`picotool`, which resets the Pico into its bootloader over USB, flashes it, and
reboots it back into the app.

Requirements:
- `firmware/redwing.uf2` must exist in the checked-out repo (built and
  committed as above) — the daemon container mounts the `firmware/` directory
  read-only (see `docker/docker-compose.yml`) and flashes whatever's at that
  path. A `git pull` alone is enough to pick up a new build; no container
  restart needed.
- Flashing briefly disconnects the RP2040 (a few seconds); the daemon's
  existing serial reconnect logic reconnects automatically once it
  re-enumerates.

To flash manually instead: hold BOOTSEL while plugging in USB, then
drag-and-drop `firmware/redwing.uf2` onto the RPI-RP2 drive that appears.
