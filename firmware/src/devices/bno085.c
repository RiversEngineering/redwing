#include "bno085.h"
#include "hardware/i2c.h"
#include "pico/stdlib.h"
#include <string.h>

// Detected I2C address (0x4A = ADDR low, 0x4B = ADDR high). Set during init.
static uint8_t _addr = 0x4Au;

// SHTP channel numbers
#define SHTP_CMD      0u   // unsolicited advertisements / product ID
#define SHTP_EXE      1u   // executable: reset, boot status
#define SHTP_CTRL     2u   // control: Set Feature commands (host → sensor)
#define SHTP_REPORTS  3u   // input reports: sensor data (sensor → host)

// SH-2 report IDs
#define RPT_LINEAR_ACCEL    0x04u
#define RPT_ROTATION_VEC    0x05u
#define CMD_SET_FEATURE     0xFDu

// Set Feature Command: 17-byte payload on channel SHTP_CTRL
// interval_us = 10000 → 100 Hz
static const uint8_t _FEAT_ROT_VEC[17] = {
    CMD_SET_FEATURE, RPT_ROTATION_VEC,
    0x00,            // flags
    0x00, 0x00,      // change sensitivity (disabled)
    0x10, 0x27, 0x00, 0x00,  // report interval = 10000 µs (100 Hz), uint32 LE
    0x00, 0x00, 0x00, 0x00,  // batch interval
    0x00, 0x00, 0x00, 0x00,  // sensor-specific config
};

static const uint8_t _FEAT_LIN_ACCEL[17] = {
    CMD_SET_FEATURE, RPT_LINEAR_ACCEL,
    0x00,
    0x00, 0x00,
    0x10, 0x27, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
};

static uint8_t _seq[6] = {0};

// Cached sensor values (Q14 for quat, Q8 for linear accel).
// Default: identity quaternion.
static int16_t _qx = 0, _qy = 0, _qz = 0, _qw = 16384;
static int16_t _ax = 0, _ay = 0, _az = 0;

// ── SHTP transport ────────────────────────────────────────────────────────────

static void shtp_write(uint8_t channel, const uint8_t *payload, uint8_t plen) {
    uint16_t total = 4u + plen;
    uint8_t buf[64];
    if (total > sizeof(buf)) return;
    buf[0] = (uint8_t)(total & 0xFFu);
    buf[1] = (uint8_t)(total >> 8u);
    buf[2] = channel;
    buf[3] = _seq[channel]++;
    memcpy(buf + 4, payload, plen);
    i2c_write_blocking(i2c0, _addr, buf, total, false);
}

// Returns payload byte count, or 0 if no data.
// channel_out: filled with the SHTP channel from the header.
static uint8_t shtp_read(uint8_t *channel_out, uint8_t *payload, uint8_t max_payload) {
    uint8_t hdr[4];
    if (i2c_read_blocking(i2c0, _addr, hdr, 4, false) != 4) return 0;

    uint16_t pkt_len = ((uint16_t)(hdr[1] & 0x7Fu) << 8u) | hdr[0];
    if (pkt_len < 5u) return 0;  // 0 = no data; 1–4 = header-only

    uint16_t payload_len = pkt_len - 4u;
    if (payload_len > max_payload) payload_len = max_payload;

    if (i2c_read_blocking(i2c0, _addr, payload, payload_len, false)
        != (int)payload_len) return 0;

    if (channel_out) *channel_out = hdr[2];
    return (uint8_t)payload_len;
}

// ── Report parsing ────────────────────────────────────────────────────────────

static void process_payload(const uint8_t *p, uint8_t len) {
    if (len < 1u) return;
    switch (p[0]) {
        case RPT_ROTATION_VEC:
            if (len < 12u) break;
            // Payload: [rpt_id][seq][status][delay][qI][qJ][qK][qReal][accuracy]
            // All multi-byte values are LE.  qI=X, qJ=Y, qK=Z, qReal=W.
            _qx = (int16_t)((p[5]  << 8) | p[4]);
            _qy = (int16_t)((p[7]  << 8) | p[6]);
            _qz = (int16_t)((p[9]  << 8) | p[8]);
            _qw = (int16_t)((p[11] << 8) | p[10]);
            break;
        case RPT_LINEAR_ACCEL:
            if (len < 10u) break;
            _ax = (int16_t)((p[5] << 8) | p[4]);
            _ay = (int16_t)((p[7] << 8) | p[6]);
            _az = (int16_t)((p[9] << 8) | p[8]);
            break;
        default: break;
    }
}

// ── Public API ────────────────────────────────────────────────────────────────

bool bno085_init(void) {
    // The BNO085 I2C hardware ACKs its address as soon as VDD is stable, but
    // the SH-2 firmware may clock-stretch on multi-byte reads during the first
    // ~500 ms of boot.  Probe with a single byte (short stretch window) and
    // retry every 50 ms for up to 600 ms.  Try both addresses.
    uint8_t dummy;
    _addr = 0;
    for (int i = 0; i < 12 && _addr == 0; i++) {
        if (i2c_read_blocking(i2c0, 0x4Au, &dummy, 1, false) >= 0)      _addr = 0x4Au;
        else if (i2c_read_blocking(i2c0, 0x4Bu, &dummy, 1, false) >= 0) _addr = 0x4Bu;
        if (_addr == 0) sleep_ms(50);
    }
    if (_addr == 0) return false;

    // Soft-reset the SH-2 firmware so we start from a known SHTP state
    // (the probe reads may have consumed a partial SHTP header).
    uint8_t rst = 0x01u;
    shtp_write(SHTP_EXE, &rst, 1);
    sleep_ms(300);

    // Drain the two unsolicited startup packets that follow a reset:
    //   channel 1 (EXE):  reset-complete  (payload[0] == 0x01)
    //   channel 0 (CMD):  advertisement
    uint8_t payload[64];
    uint8_t ch;
    bool got_reset = false;
    for (int i = 0; i < 20; i++) {
        uint8_t len = shtp_read(&ch, payload, sizeof(payload));
        if (len == 0) { sleep_ms(10); continue; }
        if (ch == SHTP_EXE && len >= 1u && payload[0] == 0x01u) got_reset = true;
        if (got_reset && ch == SHTP_CMD) break;
    }

    // Enable rotation vector and linear acceleration reports at 100 Hz.
    shtp_write(SHTP_CTRL, _FEAT_ROT_VEC,    sizeof(_FEAT_ROT_VEC));
    sleep_ms(5);
    shtp_write(SHTP_CTRL, _FEAT_LIN_ACCEL, sizeof(_FEAT_LIN_ACCEL));

    return true;
}

void bno085_poll(void) {
    uint8_t payload[64];
    uint8_t ch;
    for (int i = 0; i < 4; i++) {
        uint8_t len = shtp_read(&ch, payload, sizeof(payload));
        if (len == 0) break;
        if (ch == SHTP_REPORTS) process_payload(payload, len);
    }
}

void bno085_get_quat(int16_t *qx, int16_t *qy, int16_t *qz, int16_t *qw) {
    *qx = _qx; *qy = _qy; *qz = _qz; *qw = _qw;
}

void bno085_get_linear_accel(int16_t *ax, int16_t *ay, int16_t *az) {
    *ax = _ax; *ay = _ay; *az = _az;
}
