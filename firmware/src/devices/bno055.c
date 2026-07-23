#include "bno055.h"
#include "hardware/i2c.h"
#include "pico/stdlib.h"

#define BNO055_ADDR      0x28u
#define REG_CHIP_ID      0x00u   // expected: 0xA0
#define REG_OPR_MODE     0x3Du
#define REG_PWR_MODE     0x3Eu
#define REG_SYS_TRIGGER  0x3Fu
#define REG_PAGE_ID      0x07u
#define REG_QUAT_BASE    0x20u   // QUA_DATA_W_LSB; 8 bytes LE (W, X, Y, Z)
#define REG_LACCEL_BASE  0x28u   // LIA_DATA_X_LSB; 6 bytes LE (X, Y, Z)

#define OPR_CONFIG  0x00u
#define OPR_NDOF    0x0Cu

static bool _present = false;

static bool reg_write(uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    return i2c_write_blocking(i2c0, BNO055_ADDR, buf, 2, false) == 2;
}

static bool reg_read(uint8_t reg, uint8_t *data, uint8_t len) {
    if (i2c_write_blocking(i2c0, BNO055_ADDR, &reg, 1, true) != 1) return false;
    return i2c_read_blocking(i2c0, BNO055_ADDR, data, len, false) == (int)len;
}

bool bno055_init(void) {
    // Fast address check — if 0x28 doesn't ACK at all, bail immediately rather
    // than burning 14 × 50 ms of retries when no BNO055 is on the bus.
    uint8_t probe;
    if (i2c_read_blocking(i2c0, BNO055_ADDR, &probe, 1, false) < 0) return false;

    // BNO055 needs up to 650 ms from power-on. Retry until CHIP_ID is readable.
    uint8_t chip_id = 0;
    for (int i = 0; i < 14; i++) {
        if (reg_read(REG_CHIP_ID, &chip_id, 1) && chip_id == 0xA0u) break;
        sleep_ms(50);
    }
    if (chip_id != 0xA0u) return false;

    // Switch to CONFIG_MODE, configure, then enter NDOF fusion.
    reg_write(REG_OPR_MODE,    OPR_CONFIG);
    sleep_ms(25);
    reg_write(REG_PWR_MODE,    0x00u);  // NORMAL
    reg_write(REG_PAGE_ID,     0x00u);  // page 0
    reg_write(REG_SYS_TRIGGER, 0x00u);  // internal oscillator
    reg_write(REG_OPR_MODE,    OPR_NDOF);
    sleep_ms(20);

    _present = true;
    return true;
}

bool bno055_read(int16_t *qw, int16_t *qx, int16_t *qy, int16_t *qz,
                 int16_t *ax, int16_t *ay, int16_t *az) {
    if (!_present) return false;
    uint8_t buf[8];
    if (!reg_read(REG_QUAT_BASE, buf, 8)) return false;
    // Little-endian (LSB first) in the registers.
    *qw = (int16_t)((buf[1] << 8) | buf[0]);
    *qx = (int16_t)((buf[3] << 8) | buf[2]);
    *qy = (int16_t)((buf[5] << 8) | buf[4]);
    *qz = (int16_t)((buf[7] << 8) | buf[6]);

    uint8_t abuf[6];
    if (!reg_read(REG_LACCEL_BASE, abuf, 6)) return false;
    *ax = (int16_t)((abuf[1] << 8) | abuf[0]);
    *ay = (int16_t)((abuf[3] << 8) | abuf[2]);
    *az = (int16_t)((abuf[5] << 8) | abuf[4]);
    return true;
}
