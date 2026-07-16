"""PCA9685 I²C 16-channel PWM controller driver.

The PCA9685 is wired to the Pico's I²C0 bus (GP4/GP5, address 0x40).
All control goes through the Pico serial protocol — no direct I²C from the Pi.

All 16 channels run at 50 Hz (RC servo / ESC frequency).
The calibration routine wires PCA channel 0 to a Pico single-pin port,
has the Pico measure the actual pulse width, then corrects the PCA prescale
so that 1500 µs commands genuinely produce 1500 µs pulses.
"""

import asyncio
import json
import logging
import os

from . import protocol as proto
from .state import SharedState

log = logging.getLogger(__name__)

_DEFAULT_OSC_FREQ = 25_000_000   # 25 MHz nominal
_TARGET_HZ        = 50           # all channels at 50 Hz (servo / RC ESC)
_CAL_FILE         = "/workspace/.redwing_pca9685_cal.json"


def _calc_prescale(osc_freq: int, target_hz: float) -> int:
    return max(3, round(osc_freq / (4096 * target_hz)) - 1)


class PCA9685:
    """Asyncio-safe driver for the PCA9685 PWM controller (via Pico I²C).

    Detection and channel control are sent as protocol commands to the Pico,
    which holds the I²C bus.  The Pi never talks I²C directly.
    """

    def __init__(self, state: SharedState, rp):
        self._state = state
        self._rp = rp
        self._osc_freq = _DEFAULT_OSC_FREQ
        self._prescale = _calc_prescale(_DEFAULT_OSC_FREQ, _TARGET_HZ)
        self._present  = False
        # Last commanded pulse width per channel (for re-apply after calibration)
        self._channel_pulse_us: list[float | None] = [None] * 16

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Calibration persistence
    # ------------------------------------------------------------------

    def _load_calibration(self) -> bool:
        """Load saved calibration from disk. Returns True if loaded."""
        try:
            with open(_CAL_FILE) as f:
                data = json.load(f)
            self._osc_freq = int(data["osc_freq"])
            self._prescale = int(data["prescale"])
            log.info(
                f"PCA9685: loaded saved calibration "
                f"(osc={self._osc_freq} Hz, prescale={self._prescale})"
            )
            return True
        except (FileNotFoundError, KeyError, ValueError, OSError):
            return False

    def _save_calibration(self):
        """Persist current osc_freq and prescale to disk."""
        try:
            parent = os.path.dirname(_CAL_FILE)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(_CAL_FILE, "w") as f:
                json.dump({"osc_freq": self._osc_freq, "prescale": self._prescale}, f)
        except OSError as e:
            log.warning(f"PCA9685: could not save calibration: {e}")

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    async def detect(self) -> bool:
        """Probe for PCA9685 until found. Runs indefinitely in the background.

        Retries every 3 s while the RP2040 is not yet connected, then every
        10 s once the RP2040 is up — so plugging the PCA9685 in after the
        daemon has started is detected within 10 s.

        If a saved calibration exists it is loaded before the first pca_init,
        so the corrected prescale is applied immediately rather than the
        nominal default.
        """
        self._load_calibration()   # sets self._prescale if file exists
        calibrated = self._osc_freq != _DEFAULT_OSC_FREQ

        attempt = 0
        while True:
            found = await self._rp.pca_init(self._prescale)
            if found:
                self._present = True
                async with self._state.lock:
                    self._state.pca9685_present    = True
                    self._state.pca9685_address    = 0x40
                    self._state.pca9685_calibrated = calibrated
                    self._state.pca9685_osc_freq   = self._osc_freq
                log.info(
                    f"PCA9685 detected on Pico I²C "
                    f"(prescale={self._prescale}"
                    f"{', calibrated' if calibrated else ', nominal'})"
                )
                return True
            if self._rp.connected:
                if attempt == 0:
                    log.info("PCA9685 not detected on Pico I²C — will retry every 10 s")
                await asyncio.sleep(10.0)
            else:
                log.debug(f"PCA9685 detect attempt {attempt + 1}: RP2040 not connected yet, retrying")
                await asyncio.sleep(3.0)
            attempt += 1

    # ------------------------------------------------------------------
    # Pulse-width ↔ count conversion
    # ------------------------------------------------------------------

    def _pulse_us_to_counts(self, pulse_us: float) -> tuple[int, int]:
        period_us = (self._prescale + 1) * 4096 / self._osc_freq * 1_000_000
        off = max(0, min(4095, round(pulse_us / period_us * 4096)))
        return 0, off  # on always starts at tick 0

    # ------------------------------------------------------------------
    # Public channel control (synchronous — safe to call from asyncio)
    # ------------------------------------------------------------------

    def set_channel_pulse_us(self, channel: int, pulse_us: float):
        """Set a channel's pulse width in µs."""
        if not self._present:
            return
        on, off = self._pulse_us_to_counts(pulse_us)
        self._rp.enqueue(proto.cmd_pca_set_ch(channel, on, off))
        self._channel_pulse_us[channel] = pulse_us

    def set_channel_off(self, channel: int):
        """Disable a channel (no pulse output)."""
        if not self._present:
            return
        self._rp.enqueue(proto.cmd_pca_ch_off(channel))
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

    async def calibrate(self, pico_port_id: int) -> dict:
        """Calibrate the PCA9685 oscillator using the Pico as a pulse-width meter.

        Requires PCA channel 0 wired to a Pico single-pin port (S0–S7).
        Sets channel 0 to a nominal 1500 µs pulse, asks the Pico to measure
        the actual pulse width, then adjusts the PCA prescale so that subsequent
        1500 µs commands are accurate.

        Returns a dict: {ok, osc_freq, prescale, measured_us} on success,
        or {ok: False, error: str} on failure.
        """
        if not self._present:
            return {"ok": False, "error": "PCA9685 not detected"}

        async with self._state.lock:
            self._state.pca9685_last_calibration = None

        # Step 1: reset to nominal prescale
        nominal_prescale = _calc_prescale(_DEFAULT_OSC_FREQ, _TARGET_HZ)
        self._prescale = nominal_prescale
        self._osc_freq = _DEFAULT_OSC_FREQ
        ok = await self._rp.pca_init(nominal_prescale)
        if not ok:
            return {"ok": False, "error": "PCA9685 not responding during calibration"}

        # Step 2: set channel 0 to nominal 1500 µs (307 counts at 50 Hz)
        nominal_off = round(1500 / 20000.0 * 4096)
        self._rp.enqueue(proto.cmd_pca_set_ch(0, 0, nominal_off))

        # Step 3: wait for signal to stabilise (≥ 3 periods at 50 Hz)
        await asyncio.sleep(0.15)

        # Step 4: ask the Pico to measure the actual pulse width
        measured_us = await self._rp.measure_pulse(pico_port_id)
        if measured_us is None or measured_us < 500 or measured_us > 2500:
            return {
                "ok": False,
                "error": (
                    f"Pulse measurement out of range ({measured_us} µs). "
                    "Check that PCA channel 0 is wired to the chosen S-port."
                ),
            }

        # Step 5: derive actual oscillator frequency
        # pulse_us = nominal_off × (prescale+1) × 1e6 / osc_freq
        # → osc_freq = nominal_off × (prescale+1) × 1e6 / measured_us
        actual_osc = int(nominal_off * (nominal_prescale + 1) * 1_000_000 / measured_us)
        error_pct  = (actual_osc / _DEFAULT_OSC_FREQ - 1) * 100
        log.info(
            f"PCA9685 calibration: measured={measured_us} µs, "
            f"actual_osc={actual_osc} ({error_pct:+.2f}% vs nominal)"
        )
        self._osc_freq = actual_osc
        self._prescale = _calc_prescale(actual_osc, _TARGET_HZ)

        # Step 6: re-init with corrected prescale
        ok = await self._rp.pca_init(self._prescale)
        if not ok:
            return {"ok": False, "error": "PCA9685 not responding after calibration"}

        # Step 7: re-apply all channels that were previously set
        for ch, pulse_us in enumerate(self._channel_pulse_us):
            if pulse_us is not None:
                self.set_channel_pulse_us(ch, pulse_us)
            else:
                self.set_channel_off(ch)

        self._save_calibration()

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
