"""Battery monitor — reads a Maxim MAX17043/17048 fuel-gauge IC via I²C.

The IC is present on the DFRobot Raspberry Pi 5 UPS HAT and similar boards.
It reports state-of-charge (%) and cell voltage directly over I²C, no ADC
calibration required.

Register map (both MAX17043 and MAX17048):
  0x02  VCELL  — 12-bit cell voltage; 1 LSB = 1.25 mV (bits [15:4])
  0x04  SOC    — high byte = integer %, low byte = fractional /256 %

If smbus2 is not installed, or the IC is not found on the bus, the monitor
exits silently — battery data simply stays absent from the state broadcast.
"""

import asyncio
import logging

log = logging.getLogger(__name__)

_ADDR       = 0x36   # MAX17043/17048 fixed I²C address
_REG_VCELL  = 0x02
_REG_SOC    = 0x04

# Standard Li-Ion / 18650 discharge curve: (voltage, soc_percent) breakpoints.
# The IC's internal ModelGauge SOC requires RCOMP calibration for the specific
# cell, which we can't do without Maxim's tooling. Voltage-based SOC is less
# sophisticated but consistent and requires no calibration.
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


class BatteryMonitor:
    def __init__(self, state, bus_num: int = 1):
        self._state   = state
        self._bus_num = bus_num

    async def run(self):
        try:
            import smbus2  # noqa: F401
        except ImportError:
            log.warning("smbus2 not installed — battery monitor disabled")
            return

        log.info(f"Battery monitor starting on I²C bus {self._bus_num}")
        while True:
            try:
                voltage, soc = await asyncio.to_thread(self._read)
                async with self._state.lock:
                    self._state.battery_voltage = round(voltage, 3)
                    self._state.battery_soc     = _voltage_to_soc(voltage)
                    self._state.battery_present = True
            except Exception as exc:
                log.warning(f"Battery read failed: {exc}")
                async with self._state.lock:
                    self._state.battery_present = False
            await asyncio.sleep(5)   # fuel gauge is slow; 5 s is plenty

    def _read(self) -> tuple[float, float]:
        from smbus2 import SMBus
        with SMBus(self._bus_num) as bus:
            # VCELL: bits [15:4] × 1.25 mV gives cell voltage
            raw = bus.read_i2c_block_data(_ADDR, _REG_VCELL, 2)
            voltage = (((raw[0] << 8) | raw[1]) >> 4) * 0.00125
        # SOC is derived from voltage — the IC's ModelGauge SOC requires RCOMP
        # calibration for the specific cell; without it the register is unreliable.
        soc = _voltage_to_soc(voltage)
        return voltage, soc
