/*
 * BNO085 standalone data-streaming test
 *
 * Streams quaternion + linear acceleration to USB UART via printf.
 * Implements the exact two-transaction SHTP protocol the Adafruit BNO08x
 * library uses:
 *
 *   Txn 1 (4 bytes)   → SHTP header → gives pkt_len and channel
 *   Txn 2 (pkt_len)   → BNO085 RESTARTS from byte 0 each new transaction;
 *                        buf[0..3] = header again, buf[4..] = real payload
 *
 * After txn 2, pkt_len bytes have been delivered so the packet is closed.
 * memmove(buf, buf+4) brings the real payload to buf[0].
 *
 * GP4=SDA, GP5=SCL, I2C0, 400 kHz
 * Open the USB serial port at any baud to see output.
 */

#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"

#define SDA_PIN  4
#define SCL_PIN  5
#define BNO_ADDR 0x4Au

/* SHTP channel numbers */
#define CH_CMD     0u
#define CH_EXE     1u
#define CH_CTRL    2u
#define CH_REPORTS 3u

/* SH-2 report IDs */
#define RPT_LINEAR_ACCEL      0x04u
#define RPT_GAME_ROTATION_VEC 0x08u
#define CMD_SET_FEATURE       0xFDu

/* Set Feature Command: 10 000 µs = 100 Hz */
static const uint8_t FEAT_ROT[17] = {
    CMD_SET_FEATURE, RPT_GAME_ROTATION_VEC,
    0x00, 0x00, 0x00,
    0x10, 0x27, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
};
static const uint8_t FEAT_LIN[17] = {
    CMD_SET_FEATURE, RPT_LINEAR_ACCEL,
    0x00, 0x00, 0x00,
    0x10, 0x27, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
};

static uint8_t _seq[4] = {0};

static void shtp_write(uint8_t ch, const uint8_t *payload, uint8_t plen) {
    uint8_t buf[64];
    uint16_t total = 4u + plen;
    if (total > sizeof(buf)) return;
    buf[0] = (uint8_t)(total & 0xFF);
    buf[1] = (uint8_t)(total >> 8);
    buf[2] = ch;
    buf[3] = _seq[ch < 4 ? ch : 0]++;
    memcpy(buf + 4, payload, plen);
    int rc = i2c_write_blocking(i2c0, BNO_ADDR, buf, total, false);
    if (rc != (int)total)
        printf("  [WARN] write ch=%u FAILED rc=%d\n", ch, rc);
}

/*
 * Read one SHTP packet.
 * Returns payload byte count; 0 = empty queue or error.
 * On success: *ch_out = channel, buf[0] = report ID (real payload byte 0).
 *
 * The BNO085 restarts from byte 0 on every new I²C transaction, so txn 2
 * requests pkt_len bytes to deliver the full packet and close it.
 */
static uint16_t shtp_read(uint8_t *ch_out, uint8_t *buf, uint16_t buf_sz) {
    uint8_t hdr[4];
    if (i2c_read_blocking_until(i2c0, BNO_ADDR, hdr, 4, false,
                                make_timeout_time_ms(20)) != 4)
        return 0;

    uint16_t pkt_len = ((uint16_t)(hdr[1] & 0x7Fu) << 8u) | hdr[0];
    if (pkt_len < 5u) return 0;

    uint16_t to_read = (pkt_len <= buf_sz) ? pkt_len : buf_sz;
    if (i2c_read_blocking_until(i2c0, BNO_ADDR, buf, to_read, false,
                                make_timeout_time_ms(50)) != (int)to_read)
        return 0;

    /* buf[0..3] = header copy; real payload starts at buf[4] */
    uint16_t payload_bytes = (to_read > 4u) ? (to_read - 4u) : 0u;
    if (payload_bytes > 0u) memmove(buf, buf + 4u, payload_bytes);
    if (ch_out) *ch_out = hdr[2];
    return payload_bytes;
}

static uint32_t now_ms(void) { return to_ms_since_boot(get_absolute_time()); }

int main(void) {
    stdio_init_all();
    sleep_ms(1500);   /* let USB CDC enumerate */

    printf("\n=== BNO085 standalone streaming test ===\n");
    printf("GP%d=SDA  GP%d=SCL  I2C0  400 kHz\n\n", SDA_PIN, SCL_PIN);

    i2c_init(i2c0, 400 * 1000);
    gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(SDA_PIN);
    gpio_pull_up(SCL_PIN);
    sleep_ms(10);

    /* ── 1. Soft reset ──────────────────────────────────────────────────── */
    static const uint8_t rst[5] = {0x05, 0x00, CH_EXE, 0x00, 0x01};
    int rst_rc = i2c_write_blocking(i2c0, BNO_ADDR, rst, 5, false);
    printf("[%4lu ms] soft-reset → %s\n", (unsigned long)now_ms(),
           rst_rc == 5 ? "OK" : "NACK (using natural boot)");
    sleep_ms(rst_rc == 5 ? 1200u : 700u);

    /* ── 2. Drain advertisement in one 280-byte transaction ─────────────── */
    /*
     * Per BNO085 datasheet: bytes beyond pkt_len are padded with 0x00.
     * Reading 280 bytes delivers the full 276-byte advertisement in a single
     * I²C transaction, cleanly closing the packet.
     */
    static uint8_t big[280];
    uint32_t t = now_ms();
    int drain_rc = i2c_read_blocking_until(i2c0, BNO_ADDR, big, sizeof(big),
                                            false, make_timeout_time_ms(500));
    if (drain_rc != (int)sizeof(big)) {
        printf("[%4lu ms] ERROR: advertisement drain failed (rc=%d). "
               "Check wiring and address.\n", (unsigned long)t, drain_rc);
        while (true) sleep_ms(1000);
    }
    uint16_t adv_pkt_len = ((uint16_t)(big[1] & 0x7Fu) << 8u) | big[0];
    printf("[%4lu ms] advertisement: pkt_len=%u ch=%u — drained OK\n",
           (unsigned long)t, (unsigned)adv_pkt_len, (unsigned)big[2]);

    /* ── 3. Read EXE boot-status (ch=1, report 0x01) ────────────────────── */
    sleep_ms(50);
    static uint8_t tmp[280];
    uint8_t boot_ch = 0xFF;
    uint16_t boot_len = shtp_read(&boot_ch, tmp, sizeof(tmp));
    printf("[%4lu ms] boot-pkt: ch=%u len=%u rpt=0x%02X%s\n",
           (unsigned long)now_ms(),
           (unsigned)boot_ch, (unsigned)boot_len,
           boot_len > 0u ? (unsigned)tmp[0] : 0xFFu,
           (boot_ch == CH_EXE && boot_len > 0 && tmp[0] == 0x01)
               ? " (reset-complete ✓)" : "");

    /* ── 4. Enable sensors ───────────────────────────────────────────────── */
    sleep_ms(10);
    shtp_write(CH_CTRL, FEAT_ROT, sizeof(FEAT_ROT));
    sleep_ms(5);
    shtp_write(CH_CTRL, FEAT_LIN, sizeof(FEAT_LIN));
    printf("[%4lu ms] Set Feature sent — streaming...\n\n",
           (unsigned long)now_ms());
    sleep_ms(50);

    /* ── 5. Poll and print ───────────────────────────────────────────────── */
    /*
     * SH-2 packs multiple sub-records into one SHTP ch=3 payload.
     * Each sensor report is preceded by a 5-byte Timestamp Rebase (0xFB) or
     * Base Timestamp Reference (0xFA) record.  The parser must iterate:
     *
     *   [0xFB ts ts ts ts] [0x08 seq sts dly qx qx qy qy qz qz qw qw]  (len=17)
     *   [0xFB ts ts ts ts] [0x04 seq sts dly ax ax ay ay az az]          (len=15)
     */
    int16_t qx=0, qy=0, qz=0, qw=16384;
    int16_t ax=0, ay=0, az=0;
    uint32_t rpt_count = 0;
    uint32_t print_ts  = now_ms();
    uint32_t retry_ts  = now_ms();

    while (true) {
        uint8_t ch = 0;
        uint16_t len = shtp_read(&ch, tmp, sizeof(tmp));

        if (len > 0 && ch == CH_REPORTS) {
            /* Walk the packed payload */
            uint16_t off = 0;
            while (off < len) {
                uint8_t id = tmp[off];
                switch (id) {
                    case 0xFBu:  /* Timestamp Rebase (5 bytes) */
                    case 0xFAu:  /* Base Timestamp Reference (5 bytes) */
                        off += 5u;
                        break;
                    case RPT_GAME_ROTATION_VEC:
                        if (off + 12u > len) goto done;
                        qx = (int16_t)((tmp[off+5] << 8) | tmp[off+4]);
                        qy = (int16_t)((tmp[off+7] << 8) | tmp[off+6]);
                        qz = (int16_t)((tmp[off+9] << 8) | tmp[off+8]);
                        qw = (int16_t)((tmp[off+11] << 8) | tmp[off+10]);
                        rpt_count++;
                        off += 12u;
                        break;
                    case RPT_LINEAR_ACCEL:
                        if (off + 10u > len) goto done;
                        ax = (int16_t)((tmp[off+5] << 8) | tmp[off+4]);
                        ay = (int16_t)((tmp[off+7] << 8) | tmp[off+6]);
                        az = (int16_t)((tmp[off+9] << 8) | tmp[off+8]);
                        off += 10u;
                        break;
                    default:
                        goto done;  /* unknown record — stop safely */
                }
            }
            done:;
        }

        uint32_t n = now_ms();

        /* Re-send Set Feature every second until reports arrive */
        if (rpt_count == 0 && n - retry_ts >= 1000u) {
            retry_ts = n;
            shtp_write(CH_CTRL, FEAT_ROT, sizeof(FEAT_ROT));
            shtp_write(CH_CTRL, FEAT_LIN, sizeof(FEAT_LIN));
        }

        /* Print every 200 ms */
        if (n - print_ts >= 200u) {
            print_ts = n;
            if (rpt_count == 0) {
                printf("[%4lu ms] waiting for reports...\n", (unsigned long)n);
            } else {
                printf("[%4lu ms] rpts=%-5lu  "
                       "Q: w=%6.3f x=%6.3f y=%6.3f z=%6.3f  "
                       "Lin(Q8): x=%5d y=%5d z=%5d\n",
                       (unsigned long)n, (unsigned long)rpt_count,
                       qw / 16384.0f, qx / 16384.0f,
                       qy / 16384.0f, qz / 16384.0f,
                       (int)ax, (int)ay, (int)az);
            }
        }
    }
}
