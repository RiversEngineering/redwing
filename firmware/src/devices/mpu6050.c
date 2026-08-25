#include "mpu6050.h"
#include "../usb_comm.h"
#include "hardware/i2c.h"
#include "pico/stdlib.h"
#include <stdio.h>

#define REG_WHO_AM_I   0x75u
#define REG_PWR_MGMT1  0x6Bu
#define REG_ACCEL_BASE 0x3Bu   // ACCEL_X_H; burst-read 14 bytes for accel+temp+gyro

// WHO_AM_I values for MPU-6xxx family (all share the same register map).
// MPU-6050: 0x68, MPU-6500: 0x70, MPU-9250: 0x71
static inline bool who_am_i_ok(uint8_t who) {
    return who == 0x68u || who == 0x70u || who == 0x71u;
}

// Resolved during init — 0x68 (AD0=LOW) or 0x69 (AD0=HIGH).
static uint8_t _addr = 0u;
static bool _present = false;

static bool reg_write(uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    return i2c_write_blocking(i2c0, _addr, buf, 2, false) == 2;
}

static bool reg_read(uint8_t reg, uint8_t *data, uint8_t len) {
    // Use nostop=false (STOP then START) instead of nostop=true (REPEATED START).
    // Both are valid per I2C spec; this form is more robust on some hardware.
    if (i2c_write_blocking(i2c0, _addr, &reg, 1, false) != 1) return false;
    return i2c_read_blocking(i2c0, _addr, data, len, false) == (int)len;
}

// Probe the given I2C address for an MPU-6xxx WHO_AM_I.
// Returns the WHO_AM_I byte on success, 0 on failure.
static uint8_t probe_addr(uint8_t addr) {
    uint8_t reg = REG_WHO_AM_I;
    uint8_t who = 0;
    int wr_rc = i2c_write_blocking(i2c0, addr, &reg, 1, false);
    int rd_rc = (wr_rc == 1) ? i2c_read_blocking(i2c0, addr, &who, 1, false) : 0;
    char tmp[80];
    snprintf(tmp, sizeof(tmp), "[SENSOR] MPU 0x%02X: wr=%d rd=%d who=0x%02X",
             (unsigned)addr, wr_rc, rd_rc, (unsigned)who);
    usb_comm_send_log(tmp);
    return (wr_rc == 1 && rd_rc == 1) ? who : 0u;
}

bool mpu6050_init(void) {
    // Try both possible addresses: 0x68 (AD0=LOW) and 0x69 (AD0=HIGH).
    uint8_t who = 0;
    uint8_t addr = 0u;
    for (uint8_t candidate = 0x68u; candidate <= 0x69u; candidate++) {
        who = probe_addr(candidate);
        if (who_am_i_ok(who)) { addr = candidate; break; }
    }
    if (addr == 0u) return false;
    _addr = addr;

    reg_write(REG_PWR_MGMT1, 0x80u);  // device reset
    sleep_ms(100);
    reg_write(REG_PWR_MGMT1, 0x01u);  // wake; PLL with X-axis gyro reference

    _present = true;
    return true;
}

bool mpu6050_read(int16_t *ax, int16_t *ay, int16_t *az,
                  int16_t *gx, int16_t *gy, int16_t *gz) {
    if (!_present) return false;
    uint8_t buf[14];
    if (!reg_read(REG_ACCEL_BASE, buf, 14)) return false;

    // Data is big-endian (MSB first) in the sensor registers.
    *ax = (int16_t)((buf[0]  << 8) | buf[1]);
    *ay = (int16_t)((buf[2]  << 8) | buf[3]);
    *az = (int16_t)((buf[4]  << 8) | buf[5]);
    // buf[6-7] = temperature; skip
    *gx = (int16_t)((buf[8]  << 8) | buf[9]);
    *gy = (int16_t)((buf[10] << 8) | buf[11]);
    *gz = (int16_t)((buf[12] << 8) | buf[13]);
    return true;
}
