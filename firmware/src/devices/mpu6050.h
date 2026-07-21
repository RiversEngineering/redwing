#pragma once
#include <stdint.h>
#include <stdbool.h>

// InvenSense MPU-6050 — 6-axis IMU (3-axis accel + 3-axis gyro).
// I2C address: 0x68 (AD0=LOW) or 0x69 (AD0=HIGH).
// Default full-scale: ±2g accel (16384 LSB/g), ±250 °/s gyro (131 LSB/°/s).

bool mpu6050_init(void);
bool mpu6050_read(int16_t *ax, int16_t *ay, int16_t *az,
                  int16_t *gx, int16_t *gy, int16_t *gz);
