"""Battery monitor — auto-detects MAX17043/17048 or INA219 on the Pi's I²C bus.

Supported chips
---------------
MAX17043 / MAX17048 (Maxim)  — address 0x36 (fixed)
  Cell voltage via VCELL register (1.25 mV/LSB).

INA219 (Texas Instruments)   — address 0x40 / 0x41 / 0x44 / 0x45
  Bus voltage via Bus Voltage register (4 mV/LSB).

SOC estimation
--------------
Neither chip gives a reliable fuel-gauge reading without per-cell RCOMP
calibration.  SOC is derived from the measured voltage via a standard
Li-Ion / 18650 discharge-curve lookup table.
"""

import asyncio
import logging

from .config import BATTERY_CELLS

log = logging.getLogger(__name__)

_MAX17043_ADDR = 0x36
_INA219_ADDRS  = list(range(0x40, 0x50))  # full A1/A0 address range

# Standard Li-Ion / 18650 voltage → SOC (%) breakpoints
_VCELL_SOC_TABLE = [
    (4.20, 100.0), (4.10, 90.0), (4.00, 80.0), (3.90, 70.0),
    (3.80, 60.0),  (3.70, 50.0), (3.60, 40.0), (3.50, 30.0),
    (3.40, 20.0),  (3.30, 10.0), (3.20, 5.0),  (3.10, 2.0),
    (3.00, 0.0),
]


def _voltage_to_soc(voltage: float) -> float:
    """Estimate SOC from cell voltage via linear interpolation."""
    if voltage >= _VCELL_SOC_TABLE[0][0]:
        return 100.0
    if voltage <= _VCELL_SOC_TABLE[-1][0]:
        return 0.0
    for i in range(len(_VCELL_SOC_TABLE) - 1):
        v_hi, s_hi = _VCELL_SOC_TABLE[i]
        v_lo, s_lo = _VCELL_SOC_TABLE[i + 1]
        if v_lo <= voltage <= v_hi:
            t = (voltage - v_lo) / (v_hi - v_lo)
            return round(s_lo + t * (s_hi - s_lo), 1)
    return 0.0


def _detect_cells(voltage: float) -> int:
    """Infer series cell count from pack voltage."""
    if voltage < 5.0:
        return 1
    if voltage < 9.0:
        return 2
    if voltage < 13.0:
        return 3
    return 4


class BatteryMonitor:
    def __init__(self, state, bus_num: int = 1):
        self._state      = state
        self._bus_num    = bus_num
        self._chip: str | None = None
        self._ina219_addr: int | None = None
        self._cells: int = BATTERY_CELLS  # 0 = auto-detect on first read

    async def run(self):
        try:
            import smbus2  # noqa: F401
        except ImportError:
            log.warning("smbus2 not installed — battery monitor disabled")
            return

        self._chip, self._ina219_addr = await asyncio.to_thread(self._detect)
        if self._chip is None:
            log.warning(
                f"No battery IC found on I²C bus {self._bus_num} "
                f"(tried MAX17043 @ 0x36, INA219 @ 0x40/0x41/0x44/0x45)"
            )
            return

        addr_str = f" @ 0x{self._ina219_addr:02x}" if self._ina219_addr else ""
        log.info(f"Battery: {self._chip} on I²C bus {self._bus_num}{addr_str}")

        while True:
            try:
                voltage, _ = await asyncio.to_thread(self._read)
                if self._cells == 0:
                    self._cells = _detect_cells(voltage)
                    log.info(f"Battery: auto-detected {self._cells}S pack "
                             f"({voltage:.3f} V total)")
                cell_v = voltage / self._cells
                soc = _voltage_to_soc(cell_v)
                async with self._state.lock:
                    self._state.battery_voltage = round(voltage, 3)
                    self._state.battery_soc     = soc
                    self._state.battery_chip    = self._chip
                    self._state.battery_present = True
            except Exception as exc:
                log.warning(f"Battery read failed ({self._chip}): {exc}")
                async with self._state.lock:
                    self._state.battery_present = False
            await asyncio.sleep(5)

    # ── Detection ────────────────────────────────────────────────────────────

    def _detect(self) -> tuple[str | None, int | None]:
        from smbus2 import SMBus
        try:
            bus_ctx = SMBus(self._bus_num)
        except OSError as e:
            log.warning(f"Cannot open I²C bus {self._bus_num}: {e}")
            return None, None

        with bus_ctx as bus:
            # MAX17043/17048 — fixed address 0x36
            try:
                bus.read_i2c_block_data(_MAX17043_ADDR, 0x02, 2)  # VCELL register
                return "MAX17043", None
            except OSError:
                pass

            # INA219 — try each possible address
            for addr in _INA219_ADDRS:
                try:
                    bus.read_i2c_block_data(addr, 0x00, 2)  # CONFIG register
                    return "INA219", addr
                except OSError:
                    pass

        return None, None

    # ── Reading ──────────────────────────────────────────────────────────────

    def _read(self) -> tuple[float, float]:
        if self._chip == "MAX17043":
            return self._read_max17043()
        if self._chip == "INA219":
            return self._read_ina219()
        raise RuntimeError("No chip detected")

    def _read_max17043(self) -> tuple[float, float]:
        from smbus2 import SMBus
        with SMBus(self._bus_num) as bus:
            # VCELL register 0x02: bits [15:4], 1.25 mV/LSB
            raw = bus.read_i2c_block_data(_MAX17043_ADDR, 0x02, 2)
            voltage = (((raw[0] << 8) | raw[1]) >> 4) * 0.00125
        return voltage, _voltage_to_soc(voltage)

    def _read_ina219(self) -> tuple[float, float]:
        from smbus2 import SMBus
        with SMBus(self._bus_num) as bus:
            # Bus Voltage register 0x02: bits [15:3], 4 mV/LSB
            raw = bus.read_i2c_block_data(self._ina219_addr, 0x02, 2)
            voltage = ((raw[0] << 8 | raw[1]) >> 3) * 0.004
        return voltage, _voltage_to_soc(voltage)
