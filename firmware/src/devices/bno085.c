#include "bno085.h"
#include "../usb_comm.h"
#include "hardware/i2c.h"
#include "pico/stdlib.h"
#include <string.h>
#include <stdio.h>

// Detected I2C address (0x4A = ADDR low, 0x4B = ADDR high). Set during init.
static uint8_t _addr = 0x4Au;

// Last init diagnostic — sent periodically over USB until IMU is found.
static char _diag[128] = "";

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
    // Wait until well past the SH-2 boot window. Write probes sent during
    // early boot leave the I²C bus in a bad state when they fail; use read
    // probes only, and wait until 1500 ms from power-on.
    {
        uint32_t elapsed = to_ms_since_boot(get_absolute_time());
        if (elapsed < 1500u) sleep_ms(1500u - elapsed);
    }

    uint32_t t = to_ms_since_boot(get_absolute_time());
    _addr = 0;

    // Probe with a 4-byte read (one full SHTP header). This confirms
    // presence and leaves the bus packet-aligned for the drain below.
    uint8_t hdr[4] = {0, 0, 0, 0};
    int probe_a = i2c_read_blocking(i2c0, 0x4Au, hdr, 4, false);
    int probe_b = -1;
    if (probe_a == 4) {
        _addr = 0x4Au;
    } else {
        probe_b = i2c_read_blocking(i2c0, 0x4Bu, hdr, 4, false);
        if (probe_b == 4) _addr = 0x4Bu;
    }

    if (_addr == 0) {
        snprintf(_diag, sizeof(_diag),
            "[IMU] T=%lums: 0x4A=%s 0x4B=%s — not found",
            (unsigned long)t,
            probe_a >= 0 ? "ACK" : "NAK",
            probe_b >= 0 ? "ACK" : "NAK");
        usb_comm_send_log(_diag);
        return false;
    }

    uint16_t pkt_len = ((uint16_t)(hdr[1] & 0x7Fu) << 8u) | hdr[0];
    snprintf(_diag, sizeof(_diag),
        "[IMU] T=%lums: 0x%02X ACK hdr=%02X %02X %02X %02X pkt_len=%u — sending features",
        (unsigned long)t, _addr,
        hdr[0], hdr[1], hdr[2], hdr[3], (unsigned)pkt_len);
    usb_comm_send_log(_diag);

    // Drain the payload of the header we just consumed.
    if (pkt_len >= 5u) {
        uint8_t payload[64];
        uint16_t payload_len = pkt_len - 4u;
        if (payload_len > sizeof(payload)) payload_len = sizeof(payload);
        i2c_read_blocking(i2c0, _addr, payload, payload_len, false);
    }

    // Enable rotation vector and linear acceleration reports at 100 Hz.
    shtp_write(SHTP_CTRL, _FEAT_ROT_VEC,    sizeof(_FEAT_ROT_VEC));
    sleep_ms(5);
    shtp_write(SHTP_CTRL, _FEAT_LIN_ACCEL, sizeof(_FEAT_LIN_ACCEL));

    snprintf(_diag, sizeof(_diag),
        "[IMU] T=%lums: 0x%02X init OK (rot_vec + lin_accel at 100 Hz)",
        (unsigned long)to_ms_since_boot(get_absolute_time()), _addr);
    usb_comm_send_log(_diag);

    return true;
}

const char *bno085_get_diag(void) { return _diag; }

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
