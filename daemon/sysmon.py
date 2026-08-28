"""System resource monitor — periodic host-wide CPU/memory/temperature/disk
sampling for the dashboard's System tab.

Reads directly from /proc and /sys rather than a dependency like psutil,
matching the rest of the daemon's minimal-dependency style. The daemon
container shares the host's PID namespace (see docker-compose.yml) and,
confirmed on hardware, sees the same /proc/stat, /proc/meminfo, and thermal
zone the host itself does — no special privilege needed, these are plain
world-readable files.
"""

import asyncio
import logging
import shutil

from .state import SharedState

log = logging.getLogger(__name__)

_SAMPLE_INTERVAL = 2.0  # seconds


def _read_cpu_jiffies() -> tuple[int, int] | None:
    """Read (busy, total) jiffies from /proc/stat's aggregate 'cpu' line."""
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()
        if parts[0] != "cpu":
            return None
        values = [int(x) for x in parts[1:]]
        idle = values[3] + (values[4] if len(values) > 4 else 0)  # idle + iowait
        total = sum(values)
        return total - idle, total
    except (OSError, ValueError, IndexError):
        return None


def _read_mem_percent() -> float | None:
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                info[key] = int(rest.strip().split()[0])  # kB
        total = info.get("MemTotal")
        avail = info.get("MemAvailable")
        if total and avail is not None:
            return round((1 - avail / total) * 100, 1)
    except (OSError, ValueError, KeyError):
        pass
    return None


def _read_cpu_temp_c() -> float | None:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


def _read_disk_percent(path: str) -> float | None:
    try:
        du = shutil.disk_usage(path)
        return round(du.used / du.total * 100, 1)
    except OSError:
        return None


async def sysmon_task(state: SharedState):
    """Runs forever, sampling system load every _SAMPLE_INTERVAL seconds.

    CPU percent needs two samples spaced apart (jiffies are cumulative
    counters, not an instantaneous rate) — the first loop iteration always
    sleeps first so there's a real interval to diff against.
    """
    prev_jiffies = _read_cpu_jiffies()

    while True:
        await asyncio.sleep(_SAMPLE_INTERVAL)

        cpu_percent = None
        cur_jiffies = _read_cpu_jiffies()
        if prev_jiffies is not None and cur_jiffies is not None:
            busy_delta  = cur_jiffies[0] - prev_jiffies[0]
            total_delta = cur_jiffies[1] - prev_jiffies[1]
            if total_delta > 0:
                cpu_percent = round(max(0.0, min(100.0, busy_delta / total_delta * 100)), 1)
        prev_jiffies = cur_jiffies

        mem_percent  = _read_mem_percent()
        cpu_temp_c   = _read_cpu_temp_c()
        disk_percent = _read_disk_percent("/workspace")

        async with state.lock:
            state.sys_cpu_percent  = cpu_percent
            state.sys_mem_percent  = mem_percent
            state.sys_cpu_temp_c   = cpu_temp_c
            state.sys_disk_percent = disk_percent
