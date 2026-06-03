/**
 * VL53L0X time-of-flight distance sensor driver for RP2040.
 *
 * Ported from the Pololu VL53L0X Arduino library (MIT Licence,
 * https://github.com/pololu/vl53l0x-arduino).  Only the init and
 * continuous-ranging paths are included — no single-shot, no
 * timing-budget customisation.
 *
 * Sensor default I²C address: 0x29
 * I²C bus: i2c0, GP4 = SDA, GP5 = SCL (already initialised by caller)
 */

#include "vl53l0x.h"
#include "hardware/i2c.h"
#include "pico/time.h"
#include <string.h>

// ─── Config ───────────────────────────────────────────────────────────────────

#define VL53_ADDR        0x29u
#define CALIB_TIMEOUT_MS 1000u   // max time for each reference calibration step

// ─── Register addresses ───────────────────────────────────────────────────────

#define REG_SYSRANGE_START                          0x00u
#define REG_SYSTEM_SEQUENCE_CONFIG                  0x01u
#define REG_SYSTEM_INTERMEASUREMENT_PERIOD          0x04u
#define REG_SYSTEM_INTERRUPT_CONFIG_GPIO            0x0Au
#define REG_SYSTEM_INTERRUPT_CLEAR                  0x0Bu
#define REG_RESULT_INTERRUPT_STATUS                 0x13u
#define REG_RESULT_RANGE_STATUS                     0x14u
#define REG_MSRC_CONFIG_CONTROL                     0x60u
#define REG_FINAL_RANGE_CONFIG_MIN_COUNT_RATE       0x44u
#define REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_0        0xB0u
#define REG_GLOBAL_CONFIG_REF_EN_START_SELECT       0xB6u
#define REG_DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD     0x4Eu
#define REG_DYNAMIC_SPAD_REF_EN_START_OFFSET        0x4Fu
#define REG_GPIO_HV_MUX_ACTIVE_HIGH                 0x84u
#define REG_VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV        0x89u
#define REG_IDENTIFICATION_MODEL_ID                 0xC0u

// ─── Module state ─────────────────────────────────────────────────────────────

static uint8_t  stop_variable   = 0;
static uint16_t cached_mm       = 0;
static bool     cached_valid    = false;

// ─── Low-level I²C helpers ────────────────────────────────────────────────────

static bool wr1(uint8_t reg, uint8_t val) {
    uint8_t buf[2] = { reg, val };
    return i2c_write_blocking(i2c0, VL53_ADDR, buf, 2, false) == 2;
}

static bool rd1(uint8_t reg, uint8_t *out) {
    if (i2c_write_blocking(i2c0, VL53_ADDR, &reg, 1, true)  != 1) return false;
    if (i2c_read_blocking (i2c0, VL53_ADDR, out,  1, false) != 1) return false;
    return true;
}

static bool rdn(uint8_t reg, uint8_t *buf, uint8_t len) {
    if (i2c_write_blocking(i2c0, VL53_ADDR, &reg, 1,   true)  != 1)    return false;
    if (i2c_read_blocking (i2c0, VL53_ADDR, buf,  len, false) != len)  return false;
    return true;
}

static bool wrn(uint8_t reg, const uint8_t *buf, uint8_t len) {
    // Up to 7 data bytes plus the register address byte
    uint8_t tmp[8];
    if (len > 7) return false;
    tmp[0] = reg;
    memcpy(tmp + 1, buf, len);
    return i2c_write_blocking(i2c0, VL53_ADDR, tmp, (uint8_t)(len + 1), false)
           == (int)(len + 1);
}

// ─── SPAD info ────────────────────────────────────────────────────────────────

static bool get_spad_info(uint8_t *count, bool *is_aperture) {
    uint8_t tmp;

    wr1(0x80, 0x01); wr1(0xFF, 0x01); wr1(0x00, 0x00);

    wr1(0xFF, 0x06);
    rd1(0x83, &tmp); wr1(0x83, tmp | 0x04);
    wr1(0xFF, 0x07); wr1(0x81, 0x01);
    wr1(0x80, 0x01);
    wr1(0x94, 0x6B); wr1(0x83, 0x00);

    uint32_t deadline = to_ms_since_boot(get_absolute_time()) + CALIB_TIMEOUT_MS;
    do {
        if (!rd1(0x83, &tmp)) return false;
        if (to_ms_since_boot(get_absolute_time()) > deadline) return false;
    } while (tmp == 0x00);

    wr1(0x83, 0x01);
    if (!rd1(0x92, &tmp)) return false;
    *count       = tmp & 0x7Fu;
    *is_aperture = (tmp >> 7) & 0x01u;

    wr1(0x81, 0x00);
    wr1(0xFF, 0x06);
    rd1(0x83, &tmp); wr1(0x83, tmp & ~0x04u);
    wr1(0xFF, 0x01); wr1(0x00, 0x01);
    wr1(0xFF, 0x00); wr1(0x80, 0x00);
    return true;
}

// ─── Single reference calibration step ───────────────────────────────────────

static bool single_ref_cal(uint8_t vhv_init_byte) {
    wr1(REG_SYSRANGE_START, 0x01u | vhv_init_byte);

    uint32_t deadline = to_ms_since_boot(get_absolute_time()) + CALIB_TIMEOUT_MS;
    uint8_t  status;
    do {
        if (!rd1(REG_RESULT_INTERRUPT_STATUS, &status)) return false;
        if (to_ms_since_boot(get_absolute_time()) > deadline) return false;
    } while ((status & 0x07u) == 0);

    wr1(REG_SYSTEM_INTERRUPT_CLEAR, 0x01);
    wr1(REG_SYSRANGE_START, 0x00);
    return true;
}

// ─── Public API ───────────────────────────────────────────────────────────────

bool vl53l0x_init(void) {
    // Verify model ID
    uint8_t model_id;
    if (!rd1(REG_IDENTIFICATION_MODEL_ID, &model_id)) return false;
    if (model_id != 0xEEu) return false;

    // ── Data init ─────────────────────────────────────────────────────────────
    // Set 2V8 mode
    uint8_t v;
    if (!rd1(REG_VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV, &v)) return false;
    wr1(REG_VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV, v | 0x01u);

    wr1(0x88, 0x00);
    wr1(0x80, 0x01); wr1(0xFF, 0x01); wr1(0x00, 0x00);
    rd1(0x91, &stop_variable);
    wr1(0x00, 0x01); wr1(0xFF, 0x00); wr1(0x80, 0x00);

    // Disable MSRC + TCC limit checks
    rd1(REG_MSRC_CONFIG_CONTROL, &v);
    wr1(REG_MSRC_CONFIG_CONTROL, v | 0x12u);

    // Signal rate limit: 0.25 Mcps → fixed-point 9.7 = 0x0020
    wr1(REG_FINAL_RANGE_CONFIG_MIN_COUNT_RATE,     0x00u);
    wr1(REG_FINAL_RANGE_CONFIG_MIN_COUNT_RATE + 1, 0x20u);

    wr1(REG_SYSTEM_SEQUENCE_CONFIG, 0xFF);

    // ── Static init (tuning settings from ST / Pololu) ────────────────────────
    wr1(0xFF, 0x01); wr1(0x00, 0x00);
    wr1(0xFF, 0x00); wr1(0x09, 0x00); wr1(0x10, 0x00); wr1(0x11, 0x00);
    wr1(0x24, 0x01); wr1(0x25, 0xFF); wr1(0x75, 0x00);
    wr1(0xFF, 0x01); wr1(0x4E, 0x2C); wr1(0x48, 0x00); wr1(0x30, 0x20);
    wr1(0xFF, 0x00); wr1(0x30, 0x09); wr1(0x54, 0x00); wr1(0x31, 0x04);
    wr1(0x32, 0x03); wr1(0x40, 0x83); wr1(0x46, 0x25); wr1(0x60, 0x00);
    wr1(0x27, 0x00); wr1(0x50, 0x06); wr1(0x51, 0x00); wr1(0x52, 0x96);
    wr1(0x56, 0x08); wr1(0x57, 0x30); wr1(0x61, 0x00); wr1(0x62, 0x00);
    wr1(0x64, 0x00); wr1(0x65, 0x00); wr1(0x66, 0xA0);
    wr1(0xFF, 0x01); wr1(0x22, 0x32); wr1(0x47, 0x14); wr1(0x49, 0xFF);
    wr1(0x4A, 0x00);
    wr1(0xFF, 0x00); wr1(0x7A, 0x0A); wr1(0x7B, 0x00); wr1(0x78, 0x21);
    wr1(0xFF, 0x01); wr1(0x23, 0x34); wr1(0x42, 0x00); wr1(0x44, 0xFF);
    wr1(0x45, 0x26); wr1(0x46, 0x05); wr1(0x40, 0x40); wr1(0x0E, 0x06);
    wr1(0x20, 0x1A); wr1(0x43, 0x40);
    wr1(0xFF, 0x00); wr1(0x34, 0x03); wr1(0x35, 0x44);
    wr1(0xFF, 0x01); wr1(0x31, 0x04); wr1(0x4B, 0x09); wr1(0x4C, 0x05);
    wr1(0x4D, 0x04);
    wr1(0xFF, 0x00); wr1(0x44, 0x00); wr1(0x45, 0x20); wr1(0x47, 0x08);
    wr1(0x48, 0x28); wr1(0x67, 0x00); wr1(0x70, 0x04); wr1(0x71, 0x01);
    wr1(0x72, 0xFE); wr1(0x76, 0x00); wr1(0x77, 0x00);
    wr1(0xFF, 0x01); wr1(0x0D, 0x01);
    wr1(0xFF, 0x00); wr1(0x80, 0x01); wr1(0x01, 0xF8);
    wr1(0xFF, 0x01); wr1(0x8E, 0x01); wr1(0x00, 0x01);
    wr1(0xFF, 0x00); wr1(0x80, 0x00);

    // Set GPIO new-sample-ready interrupt, active-low
    wr1(REG_SYSTEM_INTERRUPT_CONFIG_GPIO, 0x04);
    rd1(REG_GPIO_HV_MUX_ACTIVE_HIGH, &v);
    wr1(REG_GPIO_HV_MUX_ACTIVE_HIGH, v & ~0x10u);
    wr1(REG_SYSTEM_INTERRUPT_CLEAR, 0x01);

    // Sequence config: disable MSRC + TCC
    wr1(REG_SYSTEM_SEQUENCE_CONFIG, 0xE8);

    // ── SPAD configuration ────────────────────────────────────────────────────
    uint8_t spad_count;
    bool    spad_aperture;
    if (!get_spad_info(&spad_count, &spad_aperture)) return false;

    uint8_t spad_map[6];
    if (!rdn(REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_0, spad_map, 6)) return false;

    wr1(0xFF, 0x01);
    wr1(REG_DYNAMIC_SPAD_REF_EN_START_OFFSET,  0x00);
    wr1(REG_DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD, 0x2C);
    wr1(0xFF, 0x00);
    wr1(REG_GLOBAL_CONFIG_REF_EN_START_SELECT, 0xB4);

    uint8_t first_enable  = spad_aperture ? 12u : 0u;
    uint8_t spads_enabled = 0;
    for (uint8_t i = 0; i < 48u; i++) {
        if (i < first_enable || spads_enabled == spad_count) {
            spad_map[i / 8] &= (uint8_t)(~(1u << (i % 8)));
        } else if ((spad_map[i / 8] >> (i % 8)) & 0x01u) {
            spads_enabled++;
        }
    }
    wrn(REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_0, spad_map, 6);

    // ── Reference calibration: VHV then phase ────────────────────────────────
    wr1(REG_SYSTEM_SEQUENCE_CONFIG, 0x01);
    if (!single_ref_cal(0x40)) return false;

    wr1(REG_SYSTEM_SEQUENCE_CONFIG, 0x02);
    if (!single_ref_cal(0x00)) return false;

    wr1(REG_SYSTEM_SEQUENCE_CONFIG, 0xE8);  // restore

    // ── Start continuous back-to-back ranging ─────────────────────────────────
    wr1(0x80, 0x01); wr1(0xFF, 0x01); wr1(0x00, 0x00);
    wr1(0x91, stop_variable);
    wr1(0x00, 0x01); wr1(0xFF, 0x00); wr1(0x80, 0x00);
    wr1(REG_SYSRANGE_START, 0x02);   // SYSRANGE_MODE_BACKTOBACK

    return true;
}

// Minimum signal rate for a valid reading (9.7 fixed-point, 0.25 Mcps = 0x0020).
// Below this threshold the return is optical crosstalk or noise, not a real target.
#define MIN_SIGNAL_RATE_FP  0x0020u

uint16_t vl53l0x_read_mm(bool *valid) {
    // Non-blocking: check interrupt status; update cache if new data is ready.
    uint8_t int_status;
    if (rd1(REG_RESULT_INTERRUPT_STATUS, &int_status) && (int_status & 0x07u) != 0) {
        // Read 12 bytes from RESULT_RANGE_STATUS (0x14).  Byte layout:
        //   [0]     0x14  range status  (dev_err in bits [7:3])
        //   [6:7]   0x1A  SignalRateRtnMegaCps (9.7 fixed-point)
        //   [10:11] 0x1E  RangeMilliMeter
        uint8_t buf[12];
        if (rdn(REG_RESULT_RANGE_STATUS, buf, 12)) {
            uint8_t  dev_err   = (buf[0] >> 3) & 0x0Fu;
            uint16_t signal_fp = ((uint16_t)buf[6] << 8) | buf[7];
            uint16_t range     = ((uint16_t)buf[10] << 8) | buf[11];

            cached_mm = range;
            // Accept when:
            //   dev_err 0  = no error; dev_err 11 = valid but no wrap check
            //   signal_fp  >= 0.25 Mcps (filters window crosstalk / noise)
            //   range      < 8190 mm (sensor reports this for true out-of-range)
            cached_valid = (dev_err == 0 || dev_err == 11u)
                        && signal_fp >= MIN_SIGNAL_RATE_FP
                        && range < 8190u;
        }
        wr1(REG_SYSTEM_INTERRUPT_CLEAR, 0x01);
    }
    if (valid) *valid = cached_valid;
    return cached_mm;
}

void vl53l0x_stop(void) {
    wr1(0x80, 0x01); wr1(0xFF, 0x01); wr1(0x00, 0x00);
    wr1(0x91, stop_variable);
    wr1(0x00, 0x01); wr1(0xFF, 0x00); wr1(0x80, 0x00);
    wr1(REG_SYSRANGE_START, 0x03);   // SYSRANGE_MODE_SINGLESHOT (stops continuous)
    cached_valid = false;
}
