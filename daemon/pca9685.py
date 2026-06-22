"""PCA9685 I²C 16-channel PWM controller driver.

All 16 channels run at 50 Hz (RC servo / ESC frequency).
The calibration routine wires PCA channel 0 to a Pico single-pin port,
has the Pico measure the actual pulse width, then corrects the PCA prescale
so that 1500 µs commands genuinely produce 1500 µs pulses.
"""

import asyncio
import logging
import time

from .state import SharedState

log = logging.getLogger(__name__)

# PCA9685 register map
_MODE1         = 0x00
_MODE2         = 0x01
_LED0_ON_L     = 0x06   # first channel (4 bytes per channel, auto-increment)
_ALL_LED_ON_L  = 0xFA   # broadcast: set all channels ON_L, ON_H, OFF_L, OFF_H
_ALL_LED_OFF_L = 0xFC
_PRESCALE      = 0xFE

# MODE1 bits
_MODE1_SLEEP   = 0x10
_MODE1_AI      = 0x20   # auto-increment register address

_DEFAULT_OSC_FREQ = 25_000_000   # 25 MHz nominal
_TARGET_HZ        = 50           # all channels at 50 Hz (servo / RC ESC)


def _calc_prescale(osc_freq: int, target_hz: float) -> int:
    """Compute PRE_SCALE register value for a given oscillator frequency and target Hz."""
    return max(3, round(osc_freq / (4096 * target_hz)) - 1)


class PCA9685:
    """Asyncio-safe driver for the PCA9685 PWM controller.

    I²C operations are synchronous (smbus2) but fast (~80 µs each at 400 kHz).
    Long operations (detect/init, calibration) are offloaded to a thread executor.
    Short operations (set_channel_pulse_us) run inline — blocking for <100 µs is
    acceptable in an asyncio event loop.
    """

    def __init__(self, state: SharedState, rp, i2c_bus: int = 1, address: int = 0x40):
        self._state = state
        self._rp = rp
        self._bus_num = i2c_bus
        self._address = address
        self._osc_freq = _DEFAULT_OSC_FREQ
        self._prescale = _calc_prescale(_DEFAULT_OSC_FREQ, _TARGET_HZ)
        self._i2c = None       # smbus2.SMBus, or None if not present
        self._present = False
        # Commanded pulse width per channel (for recalculation after calibration)
        self._channel_pulse_us: list[float | None] = [None] * 16

    # ------------------------------------------------------------------
    # Detection and initialisation
    # ------------------------------------------------------------------

    def _detect_and_init_sync(self) -> bool:
        """Synchronous probe + init. Runs in a thread executor."""
        try:
            from smbus2 import SMBus
        except ImportError:
            log.warning("smbus2 not installed — PCA9685 support disabled")
            return False
        try:
            bus = SMBus(self._bus_num)
            bus.read_byte_data(self._address, _MODE1)
            self._i2c = bus
        except Exception as e:
            log.debug(f"PCA9685 not found at 0x{self._address:02X} on bus {self._bus_num}: {e}")
            return False
        log.info(f"PCA9685 found at I²C 0x{self._address:02X} on bus {self._bus_num}")
        self._init_device_sync()
        return True

    def _init_device_sync(self):
        """Full PCA9685 initialisation. Sleep → set prescale → wake → all-off."""
        self._write(_MODE1, _MODE1_SLEEP)
        time.sleep(0.005)
        self._write(_PRESCALE, self._prescale)
        time.sleep(0.001)
        self._write(_MODE1, _MODE1_AI)       # wake up, enable auto-increment
        time.sleep(0.005)
        # Set all channels fully off
        self._i2c.write_i2c_block_data(self._address, _ALL_LED_ON_L,  [0x00, 0x00])
        self._i2c.write_i2c_block_data(self._address, _ALL_LED_OFF_L, [0x00, 0x10])  # FULL_OFF bit
        log.info(f"PCA9685 init: prescale={self._prescale}, osc={self._osc_freq} Hz")

    async def detect(self) -> bool:
        """Probe the I²C bus for a PCA9685. Updates state on success."""
        loop = asyncio.get_running_loop()
        found = await loop.run_in_executor(None, self._detect_and_init_sync)
        self._present = found
        if found:
            async with self._state.lock:
                self._state.pca9685_present  = True
                self._state.pca9685_address  = self._address
        return found

    # ------------------------------------------------------------------
    # Low-level I²C helpers
    # ------------------------------------------------------------------

    def _write(self, reg: int, value: int):
        self._i2c.write_byte_data(self._address, reg, value)

    def _set_channel_count(self, channel: int, on_count: int, off_count: int):
        reg = _LED0_ON_L + 4 * channel
        self._i2c.write_i2c_block_data(self._address, reg, [
            on_count  & 0xFF,
            (on_count  >> 8) & 0x0F,
            off_count & 0xFF,
            (off_count >> 8) & 0x0F,
        ])

    def _pulse_us_to_count(self, pulse_us: float) -> int:
        period_us = (self._prescale + 1) * 4096 / self._osc_freq * 1e6
        return max(0, min(4095, round(pulse_us / period_us * 4096)))

    # ------------------------------------------------------------------
    # Public channel control
    # ------------------------------------------------------------------

    def set_channel_pulse_us(self, channel: int, pulse_us: float):
        """Set a channel's pulse width in µs (synchronous, fast — safe in asyncio)."""
        if not self._present or self._i2c is None:
            return
        count = self._pulse_us_to_count(pulse_us)
        self._set_channel_count(channel, 0, count)
        self._channel_pulse_us[channel] = pulse_us

    def set_channel_off(self, channel: int):
        """Disable a channel (no pulse output)."""
        if not self._present or self._i2c is None:
            return
        reg = _LED0_ON_L + 4 * channel
        self._i2c.write_i2c_block_data(self._address, reg, [0x00, 0x00, 0x00, 0x10])
        self._channel_pulse_us[channel] = None

    def configure_channel(self, channel: int, port_type: str):
        """Configure a channel for a device type.

        Motor and servo channels get a safe 1500 µs neutral pulse immediately
        so ESCs see 'stop' before the student program runs.
        """
        if port_type in ("motor_servo_signal", "servo"):
            self.set_channel_pulse_us(channel, 1500)
        else:
            self.set_channel_off(channel)

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def _calibrate_setup_sync(self):
        """Re-init with nominal prescale and set channel 0 to nominal 1500 µs."""
        self._prescale  = _calc_prescale(_DEFAULT_OSC_FREQ, _TARGET_HZ)
        self._osc_freq  = _DEFAULT_OSC_FREQ
        self._init_device_sync()
        # Nominal 1500 µs at 50 Hz: 1500/20000 × 4096 = 307 counts
        off_count = round(1500 / 20000.0 * 4096)
        self._set_channel_count(0, 0, off_count)
        return off_count

    def _calibrate_apply_sync(self, measured_us: int, nominal_off_count: int):
        """Compute and apply corrected oscillator frequency and prescale."""
        # Derive actual osc frequency:
        # pulse_us = off_count × (prescale+1) × 1e6 / osc_freq
        # → osc_freq = off_count × (prescale+1) × 1e6 / pulse_us
        nominal_prescale = _calc_prescale(_DEFAULT_OSC_FREQ, _TARGET_HZ)
        actual_osc = int(nominal_off_count * (nominal_prescale + 1) * 1_000_000 / measured_us)
        error_pct = (actual_osc / _DEFAULT_OSC_FREQ - 1) * 100
        log.info(
            f"PCA9685 calibration: measured={measured_us} µs, "
            f"actual_osc={actual_osc} ({error_pct:+.2f}% vs nominal)"
        )
        self._osc_freq = actual_osc
        self._prescale = _calc_prescale(actual_osc, _TARGET_HZ)
        self._init_device_sync()
        # Re-apply all channels that were previously set
        for ch, pulse_us in enumerate(self._channel_pulse_us):
            if pulse_us is not None:
                self.set_channel_pulse_us(ch, pulse_us)
            else:
                self.set_channel_off(ch)

    async def calibrate(self, pico_port_id: int) -> dict:
        """Calibrate the PCA9685 oscillator using the Pico as a pulse-width meter.

        Requires PCA channel 0 wired to a Pico single-pin port (S0–S7).
        Sets channel 0 to a nominal 1500 µs pulse, asks the Pico to measure
        the actual pulse width, then adjusts the PCA prescale so that subsequent
        1500 µs commands are accurate.

        Returns a dict: {ok, osc_freq, prescale, measured_us} on success,
        or {ok: False, error: str} on failure.
        """
        if not self._present or self._i2c is None:
            return {"ok": False, "error": "PCA9685 not detected"}

        # Reset last_calibration to null so the dashboard knows calibration is in progress
        async with self._state.lock:
            self._state.pca9685_last_calibration = None

        loop = asyncio.get_running_loop()

        # Step 1: blocking — reset to nominal, set channel 0 to 1500 µs
        nominal_off_count = await loop.run_in_executor(None, self._calibrate_setup_sync)

        # Step 2: wait for signal to stabilise (3 × 50 Hz period = 60 ms minimum)
        await asyncio.sleep(0.15)

        # Step 3: ask the Pico to measure the actual pulse width
        measured_us = await self._rp.measure_pulse(pico_port_id)
        if measured_us is None or measured_us < 500 or measured_us > 2500:
            return {
                "ok": False,
                "error": f"Pulse measurement out of range ({measured_us} µs). "
                         "Check that PCA channel 0 is wired to the chosen S-port.",
            }

        # Step 4: blocking — compute corrected osc freq, update prescale, re-apply all channels
        await loop.run_in_executor(
            None, self._calibrate_apply_sync, measured_us, nominal_off_count
        )

        async with self._state.lock:
            self._state.pca9685_calibrated = True
            self._state.pca9685_osc_freq   = self._osc_freq

        return {
            "ok":          True,
            "osc_freq":    self._osc_freq,
            "prescale":    self._prescale,
            "measured_us": measured_us,
        }

    @property
    def present(self) -> bool:
        return self._present
