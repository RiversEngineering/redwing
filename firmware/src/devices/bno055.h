#pragma once
#include <stdint.h>
#include <stdbool.h>

// Bosch BNO055 — 9-axis fusion IMU (accel + gyro + magnetometer).
// I2C address: 0x28 (COM3=LOW) or 0x29 (COM3=HIGH).
// Quaternion scale: Q14 = 1 LSB/16384 (divide by 16384 to get float).
// Linear accel scale: 100 LSB/m/s² (divide by 100.0).

bool bno055_init(void);
bool bno055_read(int16_t *qw, int16_t *qx, int16_t *qy, int16_t *qz,
                 int16_t *ax, int16_t *ay, int16_t *az);
