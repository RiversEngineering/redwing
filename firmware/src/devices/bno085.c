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
    i2c_init(i2c0, 100u * 1000u);
    gpio_set_function(I2C_SDA_GPIO, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL_GPIO, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA_GPIO);
    gpio_pull_up(I2C_SCL_GPIO);
    sleep_ms(30);
}

// Returns payload byte count, or 0 if no data or timeout.
// Uses a 100 ms deadline on each read.  If the previous call timed out, a
// full I2C bus reset is performed first — this prevents the i2c->hw->enable=0
// write inside the SDK from stalling when the BNO085 is still holding SCL.
static uint8_t shtp_read(uint8_t *channel_out, uint8_t *payload, uint8_t max_payload) {
    if (_need_bus_recover) {
        _need_bus_recover = false;
        _i2c0_recover();
    }

    uint8_t hdr[4];
    if (i2c_read_blocking_until(i2c0, _addr, hdr, 4, false,
                                make_timeout_time_ms(100)) != 4) {
        _need_bus_recover = true;
        return 0;
    }

    uint16_t pkt_len = ((uint16_t)(hdr[1] & 0x7Fu) << 8u) | hdr[0];
    if (pkt_len < 5u) return 0;  // 0 = no data; 1–4 = header-only

    uint16_t payload_len = pkt_len - 4u;
    if (payload_len > max_payload) payload_len = max_payload;

    if (i2c_read_blocking_until(i2c0, _addr, payload, payload_len, false,
                                make_timeout_time_ms(100)) != (int)payload_len) {
        _need_bus_recover = true;
        return 0;
    }

    if (channel_out) *channel_out = hdr[2];
    return (uint8_t)payload_len;
}

// ── Report parsing ────────────────────────────────────────────────────────────

static void process_payload(const uint8_t *p, uint8_t len) {
    if (len < 1u) return;
    switch (p[0]) {
        // Game Rotation Vector (0x08): accel+gyro, no mag, 12-byte payload.
        // Rotation Vector     (0x05): mag-fused,          14-byte payload.
        // Both have identical quaternion layout at bytes 4–11 (Q14, LE).
        case RPT_GAME_ROTATION_VEC:
        case RPT_ROTATION_VEC:
            if (len < 12u) break;
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
    // ── Phase 1: soft-reset the BNO085 ───────────────────────────────────────
    // The BNO085 may be externally powered and have stale SHTP state from a
    // previous session (continuation bit set, high sequence number).  A write
    // on SHTP_EXE channel resets it regardless of the read-buffer state.
    // The SH-2 firmware finishes loading ~982 ms after power-on, so wait until
    // 1100 ms before attempting the write.
    {
        uint32_t t = to_ms_since_boot(get_absolute_time());
        if (t < 1100u) sleep_ms(1100u - t);
    }

    // SHTP soft-reset packet: [len_lsb=5, len_msb=0, ch=EXE, seq=0, cmd=0x01]
    static const uint8_t rst_pkt[5] = {0x05u, 0x00u, SHTP_EXE, 0x00u, 0x01u};
    uint8_t rst_addr = 0u;
    if (i2c_write_blocking(i2c0, 0x4Au, rst_pkt, 5, false) == 5) {
        rst_addr = 0x4Au;
    } else if (i2c_write_blocking(i2c0, 0x4Bu, rst_pkt, 5, false) == 5) {
        rst_addr = 0x4Bu;
    }

    {
        char tmp[72];
        snprintf(tmp, sizeof(tmp),
            "[IMU] T=%lums: soft-reset → 0x%02X %s",
            (unsigned long)to_ms_since_boot(get_absolute_time()),
            rst_addr, rst_addr ? "OK" : "NAK (not ready yet)");
        usb_comm_send_log(tmp);
    }

    // ── Phase 2: wait for boot ────────────────────────────────────────────────
    // After a successful soft-reset the BNO085 needs ~1100 ms to re-boot.
    // If the reset was NAK'd (device not ready or not present), just wait until
    // 1700 ms — the natural boot window — before probing.
    {
        uint32_t deadline = rst_addr ? 2300u : 1700u;
        uint32_t t = to_ms_since_boot(get_absolute_time());
        if (t < deadline) sleep_ms(deadline - t);
    }

    // ── Phase 3: probe ────────────────────────────────────────────────────────
    uint32_t t = to_ms_since_boot(get_absolute_time());
    _addr = 0u;

    uint8_t hdr[4] = {0, 0, 0, 0};
    int probe_a = i2c_read_blocking_until(i2c0, 0x4Au, hdr, 4, false,
                                           make_timeout_time_ms(100));
    int probe_b = -1;
    if (probe_a == 4) {
        _addr = 0x4Au;
    } else {
        probe_b = i2c_read_blocking_until(i2c0, 0x4Bu, hdr, 4, false,
                                           make_timeout_time_ms(100));
        if (probe_b == 4) _addr = 0x4Bu;
    }

    if (_addr == 0u) {
        snprintf(_diag, sizeof(_diag),
            "[IMU] T=%lums: 0x4A=%d 0x4B=%d — not found",
            (unsigned long)t, probe_a, probe_b);
        usb_comm_send_log(_diag);
        // Recover the bus so subsequent init calls (bno055, mpu6050) are unaffected.
        _i2c0_recover();
        return false;
    }

    uint16_t pkt_len = ((uint16_t)(hdr[1] & 0x7Fu) << 8u) | hdr[0];
    bool cont = (hdr[1] & 0x80u) != 0u;
    snprintf(_diag, sizeof(_diag),
        "[IMU] T=%lums: 0x%02X ACK hdr=%02X %02X %02X %02X pkt_len=%u cont=%d",
        (unsigned long)t, _addr,
        hdr[0], hdr[1], hdr[2], hdr[3], (unsigned)pkt_len, (int)cont);
    usb_comm_send_log(_diag);

    // ── Phase 4: drain exactly ONE advertisement, then pause ─────────────────
    // Without a HINT pin the BNO085 re-queues the advertisement every time the
    // host reads — it stays in "advertisement loop mode" indefinitely as long as
    // the host keeps issuing I²C reads.  The only way to break out is to stop
    // reading for long enough that the BNO085 transitions to normal mode and
    // dequeues its Product ID Response.
    //
    // Strategy:
    //   a) Read until we have consumed pkt_len-4 = 272 bytes of ch-0 payload
    //      (exactly one advertisement's worth, which the probe started).
    //   b) STOP reading entirely for 500ms (host-side silence breaks the loop).
    //   c) Send Set Feature without reading again — a Write never triggers
    //      advertisement re-loop because it is a separate I²C transaction.
    {
        uint8_t d_payload[64];
        uint8_t d_ch;
        uint32_t adv_payload   = (uint32_t)(pkt_len - 4u);  // bytes after probe hdr
        uint32_t adv_consumed  = 0;
        uint32_t d_count_ch0   = 0;

        while (adv_consumed < adv_payload) {
            uint8_t len = shtp_read(&d_ch, d_payload, sizeof(d_payload));
            if (len == 0) break;    // shouldn't happen mid-advertisement
            if (d_ch == 0u) {
                d_count_ch0++;
                adv_consumed += (uint32_t)len;
                if (adv_consumed > adv_payload) adv_consumed = adv_payload;
            }
            // Non-ch-0 packets during advertisement drain are unexpected but harmless.
        }

        {
            char tmp[80];
            snprintf(tmp, sizeof(tmp),
                "[IMU] adv drained %lu/%lu bytes in %lu reads — pausing",
                (unsigned long)adv_consumed, (unsigned long)adv_payload,
                (unsigned long)d_count_ch0);
            usb_comm_send_log(tmp);
        }

        // Host silence: BNO085 exits advertisement loop and queues Product ID.
        sleep_ms(500);

        // Send Get Product ID Request on channel 2.  This WRITE (not a read)
        // is the handshake many BNO085 firmware versions require to exit
        // advertisement mode.  After this write the BNO085 queues a Product ID
        // Response (0xF8) on channel 2 and is ready for Set Feature commands.
        static const uint8_t _get_pid[1] = {CMD_GET_PRODUCT_ID};
        shtp_write(SHTP_CTRL, _get_pid, 1u);
        sleep_ms(10);

        // Read the Product ID Response and log it so we know the BNO085
        // is out of advertisement mode.  A single read here won't re-trigger
        // the loop because the BNO085 has already exited it.
        uint8_t pid_ch;
        uint8_t pid_buf[32];
        uint8_t pid_len = shtp_read(&pid_ch, pid_buf, sizeof(pid_buf));
        {
            char tmp[64];
            snprintf(tmp, sizeof(tmp),
                "[IMU] prod_id: ch=%u len=%u rpt=0x%02X",
                (unsigned)pid_ch, (unsigned)pid_len,
                pid_len > 0u ? (unsigned)pid_buf[0] : 0xFFu);
            usb_comm_send_log(tmp);
        }
    }

    // ── Phase 5: enable sensors ───────────────────────────────────────────────
    shtp_write(SHTP_CTRL, _FEAT_ROT_VEC,   sizeof(_FEAT_ROT_VEC));
    sleep_ms(10);
    shtp_write(SHTP_CTRL, _FEAT_LIN_ACCEL, sizeof(_FEAT_LIN_ACCEL));
    sleep_ms(50);

    snprintf(_diag, sizeof(_diag),
        "[IMU] T=%lums: 0x%02X init OK (game_rot_vec + lin_accel at 100 Hz)",
        (unsigned long)to_ms_since_boot(get_absolute_time()), _addr);
    usb_comm_send_log(_diag);

    return true;
}

const char *bno085_get_diag(void) { return _diag; }

void bno085_poll(void) {
    static uint16_t _poll_ctr  = 0;
    static uint32_t _rpt_total = 0;
    static uint8_t  _ch_seen   = 0;   // resets each 200-poll window

    // If no reports yet, re-send Set Feature every 100 polls (~2 s) in case
    // the BNO085 wasn't ready when init fired the first commands.
    if (_rpt_total == 0 && _poll_ctr > 0 && (_poll_ctr % 100u) == 0u) {
        shtp_write(SHTP_CTRL, _FEAT_ROT_VEC,   sizeof(_FEAT_ROT_VEC));
        shtp_write(SHTP_CTRL, _FEAT_LIN_ACCEL, sizeof(_FEAT_LIN_ACCEL));
    }

    uint8_t payload[64];
    uint8_t ch;
    for (int i = 0; i < 8; i++) {
        uint8_t len = shtp_read(&ch, payload, sizeof(payload));
        if (len == 0) break;
        if (ch < 8u) _ch_seen |= (uint8_t)(1u << ch);
        if (ch == SHTP_REPORTS) {
            process_payload(payload, len);
            _rpt_total++;
        }
    }

    _poll_ctr++;
    // Log a status every 200 polls (~4 s at 50 Hz); reset ch_seen so each
    // window shows only what happened in that period.
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
