#include "mpu6050.h"
#include "hardware/i2c.h"
#include "pico/stdlib.h"

#define MPU6050_ADDR   0x68u
#define REG_WHO_AM_I   0x75u
#define REG_PWR_MGMT1  0x6Bu
#define REG_ACCEL_BASE 0x3Bu   // ACCEL_X_H; burst-read 14 bytes for accel+temp+gyro

// WHO_AM_I values for MPU-6xxx family (all share the same register map).
// MPU-6050: 0x68, MPU-6500: 0x70, MPU-9250: 0x71
static inline bool who_am_i_ok(uint8_t who) {
    return who == 0x68u || who == 0x70u || who == 0x71u;
}

static bool _present = false;

static bool reg_write(uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    return i2c_write_blocking(i2c0, MPU6050_ADDR, buf, 2, false) == 2;
}

static bool reg_read(uint8_t reg, uint8_t *data, uint8_t len) {
    if (i2c_write_blocking(i2c0, MPU6050_ADDR, &reg, 1, true) != 1) return false;
    return i2c_read_blocking(i2c0, MPU6050_ADDR, data, len, false) == (int)len;
}

bool mpu6050_init(void) {
    uint8_t who = 0;
    if (!reg_read(REG_WHO_AM_I, &who, 1) || !who_am_i_ok(who)) return false;

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
