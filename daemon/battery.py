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
                    self._state.battery_soc     = round(soc,     1)
                    self._state.battery_present = True
            except Exception as exc:
                log.debug(f"Battery read failed: {exc}")
                async with self._state.lock:
                    self._state.battery_present = False
            await asyncio.sleep(5)   # fuel gauge is slow; 5 s is plenty

    def _read(self) -> tuple[float, float]:
        from smbus2 import SMBus
        with SMBus(self._bus_num) as bus:
            # VCELL: bits [15:4] × 1.25 mV
            raw = bus.read_i2c_block_data(_ADDR, _REG_VCELL, 2)
            voltage = ((raw[0] << 8) | raw[1]) >> 4 * 0.00125

            # SOC: high byte = integer %, low byte = fraction/256
            raw = bus.read_i2c_block_data(_ADDR, _REG_SOC, 2)
            soc = max(0.0, min(100.0, raw[0] + raw[1] / 256.0))

        return voltage, soc
