"""PCA9685 I²C 16-channel PWM controller driver.

The PCA9685 is wired to the Pico's I²C0 bus (GP4/GP5, address 0x40).
All control goes through the Pico serial protocol — no direct I²C from the Pi.

All 16 channels share one PWM frequency, chip-wide (50 Hz — RC servo / ESC
rate) — there is no per-channel frequency on this part, only per-channel
duty within that shared period. Most channels use that period as an RC
pulse-width slot (set_channel_pulse_us); set_channel_duty instead treats it
as a plain 0-100% duty cycle for a non-RC PWM+DIR driver input, which still
works fine at 50 Hz since duty (not absolute pulse timing) is what those
drivers read.

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
_SERVO_HZ         = 50           # RC servo / ESC standard frequency
# ~1 kHz — a plain PWM+DIR motor driver input reads duty cycle directly (see
# set_channel_duty), so unlike servo mode there's no frame-timing constraint;
# 1 kHz is picked for headroom above the audible/cogging range on a small DC
# motor while staying safely below the PCA9685's hardware ceiling (~1.5 kHz
# at the minimum legal prescale of 3, and calibrated oscillators have been
# measured running a few % above nominal — see _calc_prescale's max(3, ...)).
_MOTOR_HZ         = 1000
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
        self._mode = "servo"
        self._target_hz = _SERVO_HZ
        self._prescale = _calc_prescale(_DEFAULT_OSC_FREQ, _SERVO_HZ)
        self._present  = False
        # Last commanded pulse width per channel (for re-apply after calibration)
        self._channel_pulse_us: list[float | None] = [None] * 16
        # Last commanded fixed digital level per channel (True=full-on,
        # False=full-off), for channels driven via set_channel_level rather
        # than a PWM pulse — e.g. a paired sign-magnitude motor's direction
        # line. Mutually exclusive with _channel_pulse_us; both setters clear
        # the other so calibration re-apply (below) knows which one is live.
        self._channel_level: list[bool | None] = [None] * 16
        # Last commanded duty cycle (0-100%) per channel, for a plain
        # PWM+DIR motor driver input (e.g. Cytron MDD10A Sign-Magnitude
        # mode) rather than an RC servo/ESC pulse — see set_channel_duty.
        # Also mutually exclusive with the two lists above.
        self._channel_duty: list[float | None] = [None] * 16

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Calibration persistence
    # ------------------------------------------------------------------

    def _load_calibration(self) -> bool:
        """Load saved oscillator calibration and PWM mode from disk.

        Prescale is always derived from (osc_freq, target_hz) rather than
        stored directly — osc_freq is the hardware constant a calibration
        run measures, mode/target_hz is a separate, independently-settable
        preference (see set_mode), so a prescale from a previous session
        could otherwise correspond to the wrong one of the two.
        """
        try:
            with open(_CAL_FILE) as f:
                data = json.load(f)
            self._osc_freq = int(data["osc_freq"])
            self._mode = data.get("mode", "servo")
            self._target_hz = _MOTOR_HZ if self._mode == "motor" else _SERVO_HZ
            self._prescale = _calc_prescale(self._osc_freq, self._target_hz)
            log.info(
                f"PCA9685: loaded saved settings "
                f"(osc={self._osc_freq} Hz, mode={self._mode}, prescale={self._prescale})"
            )
            return True
        except (FileNotFoundError, KeyError, ValueError, OSError):
            return False

    def _save_calibration(self):
        """Persist current osc_freq and PWM mode to disk (survives daemon restarts)."""
        try:
            parent = os.path.dirname(_CAL_FILE)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(_CAL_FILE, "w") as f:
                json.dump({"osc_freq": self._osc_freq, "mode": self._mode}, f)
        except OSError as e:
            log.warning(f"PCA9685: could not save calibration: {e}")

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    async def detect(self) -> None:
        """Probe for PCA9685 and re-verify on every Pico reconnect.

        Runs indefinitely. Retries every 3 s while the RP2040 is not yet
        connected, then every 10 s once the RP2040 is up.

        On each Pico reconnect, rp2040._connect_and_run() clears
        state.pca9685_present. This causes detect() to call pca_init()
        again and update the present flag to match reality — so removing the
        PCA9685 and power-cycling the Pico clears it from the dashboard.

        If a saved calibration exists it is loaded before the first pca_init,
        so the corrected prescale is applied immediately rather than the
        nominal default.
        """
        self._load_calibration()   # sets self._prescale if file exists
        calibrated = self._osc_freq != _DEFAULT_OSC_FREQ

        attempt = 0
        while True:
            # Check whether the Pico has cleared pca9685_present (on reconnect).
            # Only probe when: not yet confirmed present in shared state.
            async with self._state.lock:
                state_present = self._state.pca9685_present

            if not state_present:
                if self._present:
                    # Pico reconnected and cleared the flag — provisionally mark
                    # absent until pca_init() re-confirms presence.
                    self._present = False

                if self._rp.connected:
                    found = await self._rp.pca_init(self._prescale)
                    if found:
                        self._present = True
                        async with self._state.lock:
                            self._state.pca9685_present    = True
                            self._state.pca9685_address    = 0x40
                            self._state.pca9685_calibrated = calibrated
                            self._state.pca9685_osc_freq   = self._osc_freq
                            self._state.pca9685_mode       = self._mode
                        log.info(
                            f"PCA9685 detected on Pico I²C "
                            f"(prescale={self._prescale}"
                            f"{', calibrated' if calibrated else ', nominal'})"
                        )
                    else:
                        if attempt == 0:
                            log.info("PCA9685 not detected on Pico I²C — will retry every 10 s")
                        else:
                            log.debug("PCA9685 not found after Pico reconnect — will retry")

            attempt += 1
            if self._rp.connected:
                await asyncio.sleep(10.0)
            else:
                await asyncio.sleep(3.0)

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
        self._channel_level[channel] = None
        self._channel_duty[channel] = None

    def set_channel_off(self, channel: int):
        """Disable a channel (no pulse output)."""
        if not self._present:
            return
        self._rp.enqueue(proto.cmd_pca_ch_off(channel))
        self._channel_pulse_us[channel] = None
        self._channel_level[channel] = None
        self._channel_duty[channel] = None

    def set_channel_level(self, channel: int, level: bool):
        """Drive a channel to a fixed 0% or 100% duty digital level via the
        PCA9685's full-on/full-off register bits — for a paired
        sign-magnitude motor's direction line, which needs a clean high/low
        level rather than an RC-style pulse within the 50 Hz frame.
        """
        if not self._present:
            return
        if level:
            self._rp.enqueue(proto.cmd_pca_ch_on(channel))
        else:
            self._rp.enqueue(proto.cmd_pca_ch_off(channel))
        self._channel_level[channel] = level
        self._channel_pulse_us[channel] = None
        self._channel_duty[channel] = None

    def set_channel_duty(self, channel: int, duty_pct: float):
        """Set a channel's duty cycle directly (0-100%), for a plain PWM+DIR
        motor driver input (e.g. Cytron MDD10A Sign-Magnitude mode reads
        Ton/(Ton+Toff) directly) — NOT the RC servo/ESC pulse-width
        convention used by set_channel_pulse_us. That convention confines
        the signal to a narrow ~500-2500 µs slice of the 20 ms (50 Hz)
        frame — at most ~12.5% duty — which reads as "barely any power" to
        a driver that's just measuring duty cycle, regardless of how the
        daemon intended the pulse width. This scales across the *entire*
        period instead, so 100% duty is genuinely full power irrespective
        of the PCA9685's configured frequency (shared chip-wide with any
        50 Hz servos also present — see module docstring).
        """
        if not self._present:
            return
        duty_pct = max(0.0, min(100.0, duty_pct))
        if duty_pct <= 0:
            self.set_channel_off(channel)
            return
        if duty_pct >= 100:
            self.set_channel_level(channel, True)
            return
        off = max(1, min(4094, round(duty_pct / 100 * 4096)))
        self._rp.enqueue(proto.cmd_pca_set_ch(channel, 0, off))
        self._channel_duty[channel] = duty_pct
        self._channel_pulse_us[channel] = None
        self._channel_level[channel] = None

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

        # Step 1: reset to nominal prescale. Measurement always runs at the
        # servo frequency regardless of the currently-selected mode — the
        # 1500 µs nominal pulse needs a frame long enough to contain it, and
        # this exact convention is what's tested — mode is restored after
        # (step 6 uses self._target_hz, not _SERVO_HZ).
        nominal_prescale = _calc_prescale(_DEFAULT_OSC_FREQ, _SERVO_HZ)
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
        self._prescale = _calc_prescale(actual_osc, self._target_hz)

        # Step 6: re-init with corrected prescale, at whichever mode was
        # already selected before calibration started.
        ok = await self._rp.pca_init(self._prescale)
        if not ok:
            return {"ok": False, "error": "PCA9685 not responding after calibration"}

        # Step 7: re-apply all channels that were previously set. A fixed
        # digital level or a direct duty cycle doesn't depend on prescale at
        # all, but both are re-sent anyway for simplicity and to keep the
        # tracking lists authoritative for what's actually live on each
        # channel.
        for ch in range(16):
            if self._channel_level[ch] is not None:
                self.set_channel_level(ch, self._channel_level[ch])
            elif self._channel_duty[ch] is not None:
                self.set_channel_duty(ch, self._channel_duty[ch])
            elif self._channel_pulse_us[ch] is not None:
                self.set_channel_pulse_us(ch, self._channel_pulse_us[ch])
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

    # ------------------------------------------------------------------
    # PWM mode (servo vs motor) — chip-wide frequency switch
    # ------------------------------------------------------------------

    async def set_mode(self, mode: str) -> bool:
        """Switch the PCA9685's shared PWM frequency between "servo" (50 Hz,
        RC servo/ESC) and "motor" (~1 kHz, plain PWM+DIR drivers).

        Frequency is chip-wide — there is no per-channel rate on this part —
        so every existing channel's programming stops meaning what it used
        to the moment this changes. Callers are expected to have already
        reset (or be about to reset) every channel; this only reinitializes
        the chip and clears this driver's own per-channel tracking so a
        stale duty/pulse/level value can't be silently re-applied under the
        new frequency by calibrate()'s re-apply step. Returns True on success.
        """
        if mode not in ("servo", "motor"):
            return False
        target_hz = _MOTOR_HZ if mode == "motor" else _SERVO_HZ
        prescale = _calc_prescale(self._osc_freq, target_hz)
        ok = await self._rp.pca_init(prescale)
        if not ok:
            return False
        self._mode = mode
        self._target_hz = target_hz
        self._prescale = prescale
        self._channel_pulse_us = [None] * 16
        self._channel_level    = [None] * 16
        self._channel_duty     = [None] * 16
        self._save_calibration()
        async with self._state.lock:
            self._state.pca9685_mode = self._mode
        return True

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def target_hz(self) -> float:
        return self._target_hz

    @property
    def present(self) -> bool:
        return self._present
