#include "bno085.h"
#include "../usb_comm.h"
#include "../protocol.h"
#include "hardware/i2c.h"
#include "hardware/resets.h"
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
#define RPT_LINEAR_ACCEL        0x04u
#define RPT_ROTATION_VEC        0x05u   // magnetometer-fused, needs calibration
#define RPT_GAME_ROTATION_VEC   0x08u   // accel+gyro only, starts immediately
#define CMD_SET_FEATURE         0xFDu
#define CMD_GET_PRODUCT_ID      0xF9u

// Set Feature Command: 17-byte payload on channel SHTP_CTRL
// interval_us = 10000 → 100 Hz
// Use Game Rotation Vector (0x08): accel+gyro fusion only, no magnetometer
// calibration required — outputs immediately on first boot.
static const uint8_t _FEAT_ROT_VEC[17] = {
    CMD_SET_FEATURE, RPT_GAME_ROTATION_VEC,
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

static const uint8_t _FEAT_ACCEL[17] = {
    CMD_SET_FEATURE, 0x01u,  // Accelerometer — fallback; confirms ch=3 reports flow
    0x00,
    0x00, 0x00,
    0x10, 0x27, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
};

static uint8_t _seq[6] = {0};

// Set when shtp_read() times out; the next call will do a full I2C bus reset
// before trying again, bypassing the enable=0 hang that occurs when the
// BNO085 is still holding SCL low after a software-aborted transaction.
static bool _need_bus_recover = false;

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
    int rc = i2c_write_blocking(i2c0, _addr, buf, total, false);
    if (rc != (int)total) {
        char tmp[64];
        snprintf(tmp, sizeof(tmp),
            "[IMU] shtp_write ch=%u len=%u FAILED rc=%d", channel, total, rc);
        usb_comm_send_log(tmp);
    }
}

// Force-reset the I2C0 peripheral via the RP2040 resets block.
// Unlike i2c->hw->enable = 0 (which stalls when the slave holds SCL low),
// reset_block() is an unconditional register write that never waits for the
// bus — safe to call while the BNO085 is mid-clock-stretch.
// After the reset, sleep 30 ms so the BNO085's internal SCL-idle watchdog
// (~25 ms) has time to fire and release the bus.
static void _i2c0_recover(void) {
    reset_block(RESETS_RESET_I2C0_BITS);
    unreset_block_wait(RESETS_RESET_I2C0_BITS);
    i2c_init(i2c0, 400u * 1000u);
    gpio_set_function(I2C_SDA_GPIO, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL_GPIO, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA_GPIO);
    gpio_pull_up(I2C_SCL_GPIO);
    sleep_ms(30);
}

// Returns payload byte count (0 = no data / timeout).
// On success, payload[0] is the SHTP report ID (real payload byte 0).
//
// The BNO085's I²C slave RESTARTS FROM BYTE 0 of the current packet on every
// new I²C read transaction.  Two-transaction reads therefore work as follows:
//
//   Txn 1 (4 bytes) → receives SHTP header bytes [0..3]  → gives pkt_len / ch
//   Txn 2 (pkt_len bytes) → BNO085 restarts; delivers full packet [0..pkt_len-1]
//                             buf[0..3] = header again, buf[4..] = real payload
//
// After txn 2, pkt_len bytes have been delivered from byte 0 → packet is done.
// We memmove(payload, payload+4, pkt_len-4) so callers see payload[0] = report ID.
//
// max_buf must be >= pkt_len for a full delivery; 280 bytes covers all SHTP packets.
static uint16_t shtp_read(uint8_t *channel_out, uint8_t *payload, uint16_t max_buf) {
    if (_need_bus_recover) {
        _need_bus_recover = false;
        _i2c0_recover();
    }

    // Transaction 1: 4-byte header only
    uint8_t hdr[4];
    if (i2c_read_blocking_until(i2c0, _addr, hdr, 4, false,
                                make_timeout_time_ms(200)) != 4) {
        _need_bus_recover = true;
        return 0;
    }

    uint16_t pkt_len = ((uint16_t)(hdr[1] & 0x7Fu) << 8u) | hdr[0];
    if (pkt_len < 5u) return 0;

    // Transaction 2: full pkt_len bytes (BNO085 restarts from byte 0)
    uint16_t to_read = (pkt_len <= max_buf) ? pkt_len : max_buf;
    if (i2c_read_blocking_until(i2c0, _addr, payload, to_read, false,
                                make_timeout_time_ms(200)) != (int)to_read) {
        _need_bus_recover = true;
        return 0;
    }

    // payload[0..3] = header again; real payload starts at payload[4].
    // Move it to the front so callers see payload[0] = report ID.
    uint16_t payload_bytes;
    if (to_read >= pkt_len) {
        payload_bytes = pkt_len - 4u;
        memmove(payload, payload + 4u, payload_bytes);
    } else if (to_read > 4u) {
        payload_bytes = to_read - 4u;
        memmove(payload, payload + 4u, payload_bytes);
    } else {
        payload_bytes = 0u;
    }

    if (channel_out) *channel_out = hdr[2];
    return payload_bytes;
}

// ── Report parsing ────────────────────────────────────────────────────────────

// SH-2 packs multiple sub-records into one SHTP ch=3 payload.
// A 5-byte Timestamp Rebase (0xFB) or Base Timestamp Reference (0xFA) record
// precedes each sensor report.  Walk the full payload to find them all.
static void process_payload(const uint8_t *p, uint16_t len) {
    uint16_t off = 0;
    while (off < len) {
        uint8_t id = p[off];
        switch (id) {
            case 0xFBu:  // Timestamp Rebase (5 bytes)
            case 0xFAu:  // Base Timestamp Reference (5 bytes)
                off += 5u;
                break;
            case RPT_GAME_ROTATION_VEC:
            case RPT_ROTATION_VEC:
                if (off + 12u > len) return;
                _qx = (int16_t)((p[off+5] << 8) | p[off+4]);
                _qy = (int16_t)((p[off+7] << 8) | p[off+6]);
                _qz = (int16_t)((p[off+9] << 8) | p[off+8]);
                _qw = (int16_t)((p[off+11] << 8) | p[off+10]);
                off += 12u;
                break;
            case RPT_LINEAR_ACCEL:
                if (off + 10u > len) return;
                _ax = (int16_t)((p[off+5] << 8) | p[off+4]);
                _ay = (int16_t)((p[off+7] << 8) | p[off+6]);
                _az = (int16_t)((p[off+9] << 8) | p[off+8]);
                off += 10u;
                break;
            default:
                return;  // unknown record type — stop safely
        }
    }
}

// ── Public API ────────────────────────────────────────────────────────────────

bool bno085_init(void) {
    // ── Phase 1: soft reset ───────────────────────────────────────────────────
    {
        uint32_t t = to_ms_since_boot(get_absolute_time());
        if (t < 1100u) sleep_ms(1100u - t);
    }
    static const uint8_t rst_pkt[5] = {0x05u, 0x00u, SHTP_EXE, 0x00u, 0x01u};
    uint8_t rst_addr = 0u;
    if (i2c_write_blocking(i2c0, 0x4Au, rst_pkt, 5, false) == 5) rst_addr = 0x4Au;
    else if (i2c_write_blocking(i2c0, 0x4Bu, rst_pkt, 5, false) == 5) rst_addr = 0x4Bu;

    // Fast exit: neither address ACKed — no BNO085 on this bus.
    // Both probes use i2c_write_blocking with nostop=false, whose abort path
    // waits for STOP_DET before returning, leaving the bus clean.  No peripheral
    // reset is needed; the next I2C caller (mpu6050_init, bno055_init) can
    // proceed immediately.
    if (rst_addr == 0u) {
        snprintf(_diag, sizeof(_diag), "[IMU] not found");
        return false;
    }

    {
        char tmp[64];
        snprintf(tmp, sizeof(tmp), "[IMU] T=%lums: soft-reset → 0x%02X OK",
            (unsigned long)to_ms_since_boot(get_absolute_time()), rst_addr);
        usb_comm_send_log(tmp);
    }

    // ── Phase 2: wait for BNO085 boot ────────────────────────────────────────
    {
        uint32_t t = to_ms_since_boot(get_absolute_time());
        if (t < 2300u) sleep_ms(2300u - t);
    }

    // ── Phase 3+4: single-transaction probe + drain ───────────────────────────
    // The BNO085 only transitions from advertisement mode to normal mode when the
    // host reads the ENTIRE advertisement in a SINGLE I²C transaction (no STOP
    // mid-packet).  Two transactions (probe 4 bytes → STOP, drain 272 bytes →
    // STOP) leave the BNO085 in advertisement mode no matter how they are ordered.
    //
    // Per the BNO085 datasheet: if the host requests more bytes than the packet
    // length, the remaining bytes are padded with 0x00.  Reading 280 bytes for a
    // 276-byte advertisement therefore delivers [header(4)][payload(272)][zeros(4)]
    // in one shot, cleanly closing the packet.
    uint32_t t = to_ms_since_boot(get_absolute_time());
    _addr = 0u;
    static uint8_t big_buf[280];
    memset(big_buf, 0, sizeof(big_buf));
    if (i2c_read_blocking_until(i2c0, rst_addr, big_buf, sizeof(big_buf), false,
                                 make_timeout_time_ms(500)) == (int)sizeof(big_buf)) {
        _addr = rst_addr;
    }
    if (_addr == 0u) {
        snprintf(_diag, sizeof(_diag), "[IMU] T=%lums: 0x%02X found but boot read failed",
                 (unsigned long)t, rst_addr);
        usb_comm_send_log(_diag);
        // BNO085 was found but didn't complete boot — it may be holding SCL low.
        _i2c0_recover();
        return false;
    }
    {
        uint16_t pkt_len = ((uint16_t)(big_buf[1] & 0x7Fu) << 8u) | big_buf[0];
        uint8_t  ch      = big_buf[2];
        snprintf(_diag, sizeof(_diag),
            "[IMU] T=%lums: 0x%02X pkt_len=%u ch=%u p0=0x%02X (single-txn drain)",
            (unsigned long)t, _addr, (unsigned)pkt_len, (unsigned)ch,
            (unsigned)big_buf[4]);
        usb_comm_send_log(_diag);
    }

    // ── Phase 4.5: read EXE boot-status before sending any feature commands ──
    // After a reset the BNO085 queues a boot-status notification on channel 1
    // (report 0x05).  It discards CTRL writes that arrive while this packet is
    // still pending — the SH-2 library always reads it before commanding anything.
    sleep_ms(50);
    {
        static uint8_t exe_buf[32];
        uint8_t  exe_ch  = 0xFF;
        uint16_t exe_len = shtp_read(&exe_ch, exe_buf, sizeof(exe_buf));
        char tmp[80];
        snprintf(tmp, sizeof(tmp),
            "[IMU] boot-pkt: ch=%u len=%u rpt=0x%02X",
            (unsigned)exe_ch, (unsigned)exe_len,
            exe_len > 0u ? (unsigned)exe_buf[0] : 0xFFu);
        usb_comm_send_log(tmp);
    }

    // ── Phase 5: enable sensors ───────────────────────────────────────────────
    sleep_ms(10);
    shtp_write(SHTP_CTRL, _FEAT_ROT_VEC,   sizeof(_FEAT_ROT_VEC));
    sleep_ms(5);
    shtp_write(SHTP_CTRL, _FEAT_LIN_ACCEL, sizeof(_FEAT_LIN_ACCEL));
    sleep_ms(5);
    shtp_write(SHTP_CTRL, _FEAT_ACCEL,     sizeof(_FEAT_ACCEL));
    sleep_ms(50);

    snprintf(_diag, sizeof(_diag),
        "[IMU] T=%lums: 0x%02X init OK",
        (unsigned long)to_ms_since_boot(get_absolute_time()), _addr);
    usb_comm_send_log(_diag);

    return true;
}

const char *bno085_get_diag(void) { return _diag; }

void bno085_poll(void) {
    static uint16_t _poll_ctr     = 0;
    static uint32_t _rpt_total    = 0;
    static uint8_t  _ch_seen      = 0;
    static bool     _logged_nonch0 = false;

    // Re-send all three Set Feature writes every 50 polls (~1 s) until reports arrive.
    if (_rpt_total == 0 && _poll_ctr > 0 && (_poll_ctr % 50u) == 0u) {
        shtp_write(SHTP_CTRL, _FEAT_ROT_VEC,   sizeof(_FEAT_ROT_VEC));
        shtp_write(SHTP_CTRL, _FEAT_LIN_ACCEL, sizeof(_FEAT_LIN_ACCEL));
        shtp_write(SHTP_CTRL, _FEAT_ACCEL,     sizeof(_FEAT_ACCEL));
    }

    // 280-byte buffer: large enough to read a 272-byte advertisement payload in
    // ONE I²C transaction (the same way the Adafruit/SH-2 library does it).
    // Chunked 64-byte reads keep the BNO085 stuck in advertisement mode.
    static uint8_t payload[280];
    uint8_t ch;
    for (int i = 0; i < 8; i++) {
        uint16_t len = shtp_read(&ch, payload, sizeof(payload));
        if (len == 0) break;
        if (ch < 8u) _ch_seen |= (uint8_t)(1u << ch);
        if (!_logged_nonch0 && ch != SHTP_CMD) {
            _logged_nonch0 = true;
            char tmp[64];
            snprintf(tmp, sizeof(tmp),
                "[IMU] first non-ch0: ch=%u rpt=0x%02X after %u polls",
                (unsigned)ch,
                len > 0u ? (unsigned)payload[0] : 0xFFu,
                (unsigned)_poll_ctr);
            usb_comm_send_log(tmp);
        }
        if (ch == SHTP_REPORTS) {
            process_payload(payload, len);
            _rpt_total++;
        }
    }

    _poll_ctr++;
    if (_poll_ctr >= 200u) {
        _poll_ctr = 0;
        char tmp[80];
        if (_rpt_total == 0) {
            snprintf(tmp, sizeof(tmp),
                "[IMU] no reports; ch_seen=0x%02X", (unsigned)_ch_seen);
        } else {
            snprintf(tmp, sizeof(tmp),
                "[IMU] %lu rpts qw=%d qx=%d qy=%d qz=%d",
                (unsigned long)_rpt_total,
                (int)_qw, (int)_qx, (int)_qy, (int)_qz);
        }
        _ch_seen = 0;
        usb_comm_send_log(tmp);
    }
}

void bno085_get_quat(int16_t *qx, int16_t *qy, int16_t *qz, int16_t *qw) {
    *qx = _qx; *qy = _qy; *qz = _qz; *qw = _qw;
}

void bno085_get_linear_accel(int16_t *ax, int16_t *ay, int16_t *az) {
    *ax = _ax; *ay = _ay; *az = _az;
}
